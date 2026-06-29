from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role
from accounts.roles import (
    AccountRole,
    StaffAccessLevel,
    get_role_label,
    get_role_rank,
    get_staff_access_level_label,
)
from customers.models import Customer
from inventory.models import InventoryBatch
from orders.models import Order
from products.models import Product

User = get_user_model()


INTERNAL_ACCOUNT_ROLES = frozenset(
    {
        AccountRole.OWNER,
        AccountRole.FULL_STAFF,
        AccountRole.RESTRICTED_STAFF,
    }
)

ACCOUNT_ACTIVITY_LIMIT = 24


@dataclass(frozen=True, slots=True)
class AccountListRow:
    user_id: int
    email: str
    account_role: AccountRole
    role_label: str
    linked_identity: str
    linked_identity_href: str
    status_label: str
    is_active: bool
    last_login: datetime | None
    date_joined: datetime


@dataclass(frozen=True, slots=True)
class AccountActivityRow:
    occurred_at: datetime
    occurred_at_label: str
    event_label: str
    target_label: str
    target_href: str
    meta: str
    tone: str


@dataclass(frozen=True, slots=True)
class ResolvedAccountIdentity:
    account_role: AccountRole
    role_label: str
    linked_identity: str
    linked_identity_href: str = ""


@dataclass(frozen=True, slots=True)
class ActivitySpec:
    model: type
    actor_field: str
    occurred_at_field: str
    event_label: str
    route_name: str
    route_kwarg: str
    target_label: Callable[[object], str]
    meta: Callable[[object], str]
    tone: str
    select_related: tuple[str, ...] = ()


ORDER_ACTIVITY_SPECS = (
    ActivitySpec(
        model=Order,
        actor_field="placed_by",
        occurred_at_field="placed_at",
        event_label=_("Placed order"),
        route_name="orders:detail",
        route_kwarg="order_id",
        target_label=lambda order: _("Order #%(order_id)s") % {"order_id": order.pk},
        meta=lambda order: order.customer_name,
        tone="warning",
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="packed_by",
        occurred_at_field="packed_at",
        event_label=_("Packed order"),
        route_name="orders:detail",
        route_kwarg="order_id",
        target_label=lambda order: _("Order #%(order_id)s") % {"order_id": order.pk},
        meta=lambda order: order.customer_name,
        tone="info",
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="delivered_by",
        occurred_at_field="delivered_at",
        event_label=_("Delivered order"),
        route_name="orders:detail",
        route_kwarg="order_id",
        target_label=lambda order: _("Order #%(order_id)s") % {"order_id": order.pk},
        meta=lambda order: order.customer_name,
        tone="success",
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="cancelled_by",
        occurred_at_field="cancelled_at",
        event_label=_("Cancelled order"),
        route_name="orders:detail",
        route_kwarg="order_id",
        target_label=lambda order: _("Order #%(order_id)s") % {"order_id": order.pk},
        meta=lambda order: order.customer_name,
        tone="danger",
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        event_label=_("Edited order"),
        route_name="orders:detail",
        route_kwarg="order_id",
        target_label=lambda order: _("Order #%(order_id)s") % {"order_id": order.pk},
        meta=lambda order: order.customer_name,
        tone="neutral",
        select_related=("customer",),
    ),
)


PRODUCT_ACTIVITY_SPECS = (
    ActivitySpec(
        model=Product,
        actor_field="created_by",
        occurred_at_field="created_at",
        event_label="Created product",
        route_name="products:detail",
        route_kwarg="product_pk",
        target_label=lambda product: product.display_name,
        meta=lambda product: product.code_label,
        tone="success",
    ),
    ActivitySpec(
        model=Product,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        event_label="Edited product",
        route_name="products:detail",
        route_kwarg="product_pk",
        target_label=lambda product: product.display_name,
        meta=lambda product: product.code_label,
        tone="neutral",
    ),
    ActivitySpec(
        model=Product,
        actor_field="activated_by",
        occurred_at_field="activated_at",
        event_label="Activated product",
        route_name="products:detail",
        route_kwarg="product_pk",
        target_label=lambda product: product.display_name,
        meta=lambda product: product.code_label,
        tone="success",
    ),
    ActivitySpec(
        model=Product,
        actor_field="deactivated_by",
        occurred_at_field="deactivated_at",
        event_label="Deactivated product",
        route_name="products:detail",
        route_kwarg="product_pk",
        target_label=lambda product: product.display_name,
        meta=lambda product: product.code_label,
        tone="muted",
    ),
)


INVENTORY_ACTIVITY_SPECS = (
    ActivitySpec(
        model=InventoryBatch,
        actor_field="created_by",
        occurred_at_field="created_at",
        event_label="Added batch",
        route_name="inventory:detail",
        route_kwarg="batch_pk",
        target_label=lambda batch: batch.batch_id,
        meta=lambda batch: batch.product.display_name,
        tone="success",
        select_related=("product",),
    ),
    ActivitySpec(
        model=InventoryBatch,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        event_label="Edited batch",
        route_name="inventory:detail",
        route_kwarg="batch_pk",
        target_label=lambda batch: batch.batch_id,
        meta=lambda batch: batch.product.display_name,
        tone="neutral",
        select_related=("product",),
    ),
    ActivitySpec(
        model=InventoryBatch,
        actor_field="closed_by",
        occurred_at_field="closed_at",
        event_label="Closed batch",
        route_name="inventory:detail",
        route_kwarg="batch_pk",
        target_label=lambda batch: batch.batch_id,
        meta=lambda batch: batch.product.display_name,
        tone="muted",
        select_related=("product",),
    ),
)


CUSTOMER_ACTIVITY_SPECS = (
    ActivitySpec(
        model=Customer,
        actor_field="created_by",
        occurred_at_field="created_at",
        event_label="Created customer",
        route_name="customers:detail",
        route_kwarg="customer_pk",
        target_label=lambda customer: customer.name,
        meta=lambda customer: customer.email,
        tone="success",
    ),
    ActivitySpec(
        model=Customer,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        event_label="Edited customer",
        route_name="customers:detail",
        route_kwarg="customer_pk",
        target_label=lambda customer: customer.name,
        meta=lambda customer: customer.email,
        tone="neutral",
    ),
    ActivitySpec(
        model=Customer,
        actor_field="activated_by",
        occurred_at_field="activated_at",
        event_label="Activated customer",
        route_name="customers:detail",
        route_kwarg="customer_pk",
        target_label=lambda customer: customer.name,
        meta=lambda customer: customer.email,
        tone="success",
    ),
    ActivitySpec(
        model=Customer,
        actor_field="deactivated_by",
        occurred_at_field="deactivated_at",
        event_label="Deactivated customer",
        route_name="customers:detail",
        route_kwarg="customer_pk",
        target_label=lambda customer: customer.name,
        meta=lambda customer: customer.email,
        tone="muted",
    ),
)


ACCOUNT_ACTIVITY_SPECS = (
    *ORDER_ACTIVITY_SPECS,
    *PRODUCT_ACTIVITY_SPECS,
    *INVENTORY_ACTIVITY_SPECS,
    *CUSTOMER_ACTIVITY_SPECS,
)


def get_account_user(*, user_id: int):
    return get_object_or_404(
        User.objects.select_related(
            "staff_account",
            "customer_membership__customer",
        ),
        pk=user_id,
    )


def get_account_row(*, user) -> AccountListRow:
    return _build_account_row(user)


def list_internal_account_rows(*, sort: str) -> tuple[AccountListRow, ...]:
    return _list_account_rows_for_roles(
        roles=INTERNAL_ACCOUNT_ROLES,
        sort=sort,
    )


def list_customer_account_rows(*, sort: str) -> tuple[AccountListRow, ...]:
    return _list_account_rows_for_roles(
        roles=frozenset({AccountRole.CUSTOMER}),
        sort=sort,
    )


def list_unlinked_account_rows(*, sort: str) -> tuple[AccountListRow, ...]:
    return _list_account_rows_for_roles(
        roles=frozenset({AccountRole.UNKNOWN}),
        sort=sort,
    )


def list_account_activity_rows(
    *,
    user,
    use_customer_portal_links: bool = False,
) -> tuple[AccountActivityRow, ...]:
    rows = _activity_rows_from_specs(
        user=user,
        specs=ACCOUNT_ACTIVITY_SPECS,
        use_customer_portal_links=use_customer_portal_links,
    )

    return tuple(
        sorted(
            rows,
            key=lambda row: row.occurred_at,
            reverse=True,
        )[:ACCOUNT_ACTIVITY_LIMIT]
    )


def _list_account_rows_for_roles(
    *,
    roles: frozenset[AccountRole],
    sort: str,
) -> tuple[AccountListRow, ...]:
    rows = tuple(row for row in _list_all_account_rows() if row.account_role in roles)

    return _sort_account_rows(rows=rows, sort=sort)


def _list_all_account_rows() -> tuple[AccountListRow, ...]:
    users = User.objects.select_related(
        "staff_account",
        "customer_membership__customer",
    ).order_by("email", "username")

    return tuple(_build_account_row(user) for user in users)


def _build_account_row(user) -> AccountListRow:
    identity = _resolve_account_identity(user)

    return AccountListRow(
        user_id=user.pk,
        email=user.email or user.username,
        account_role=identity.account_role,
        role_label=identity.role_label,
        linked_identity=identity.linked_identity,
        linked_identity_href=identity.linked_identity_href,
        status_label=_status_label(user=user),
        is_active=user.is_active,
        last_login=user.last_login,
        date_joined=user.date_joined,
    )


def _resolve_account_identity(user) -> ResolvedAccountIdentity:
    account_role = _resolve_safe_account_role(user)

    if account_role == AccountRole.OWNER:
        return ResolvedAccountIdentity(
            account_role=account_role,
            role_label=get_role_label(account_role),
            linked_identity=_("Superuser"),
        )

    if _has_staff_account(user) and _has_customer_membership(user):
        customer = user.customer_membership.customer

        return ResolvedAccountIdentity(
            account_role=account_role,
            role_label=_("Invalid identity"),
            linked_identity=_("Staff and customer · %(customer)s")
            % {
                "customer": customer.name,
            },
            linked_identity_href=_customer_detail_href(customer),
        )

    if account_role in {
        AccountRole.FULL_STAFF,
        AccountRole.RESTRICTED_STAFF,
    }:
        return ResolvedAccountIdentity(
            account_role=account_role,
            role_label=get_role_label(account_role),
            linked_identity=_staff_identity_label(user.staff_account.access_level),
        )

    if account_role == AccountRole.CUSTOMER:
        customer = user.customer_membership.customer

        return ResolvedAccountIdentity(
            account_role=account_role,
            role_label=get_role_label(account_role),
            linked_identity=customer.name,
            linked_identity_href=_customer_detail_href(customer),
        )

    if _has_staff_account(user):
        return ResolvedAccountIdentity(
            account_role=account_role,
            role_label=_("Invalid staff account"),
            linked_identity=_("Internal staff"),
        )

    if _has_customer_membership(user):
        customer = user.customer_membership.customer

        return ResolvedAccountIdentity(
            account_role=account_role,
            role_label=_("Invalid customer account"),
            linked_identity=customer.name,
            linked_identity_href=_customer_detail_href(customer),
        )

    return ResolvedAccountIdentity(
        account_role=account_role,
        role_label=get_role_label(account_role),
        linked_identity="—",
    )


def _resolve_safe_account_role(user) -> AccountRole:
    try:
        return resolve_account_role(user)
    except InvalidAccountIdentity:
        return AccountRole.UNKNOWN


def _customer_detail_href(customer: Customer) -> str:
    return reverse(
        "customers:detail",
        kwargs={"customer_pk": customer.pk},
    )


def _staff_identity_label(access_level: StaffAccessLevel | str) -> str:
    return _("Internal staff · %(access_level)s") % {
        "access_level": get_staff_access_level_label(access_level),
    }


def _status_label(*, user) -> str:
    if user.is_active:
        return _("Active")

    return _("Inactive")


def _sort_account_rows(
    *,
    rows: tuple[AccountListRow, ...],
    sort: str,
) -> tuple[AccountListRow, ...]:
    reverse = sort.startswith("-")
    sort_key = sort.removeprefix("-")

    return tuple(
        sorted(
            rows,
            key=_account_sort_key(sort_key),
            reverse=reverse,
        )
    )


def _account_sort_key(sort_key: str):
    if sort_key == "role":
        return _role_sort_key

    if sort_key == "linked":
        return _linked_identity_sort_key

    if sort_key == "status":
        return _status_sort_key

    if sort_key == "last_login":
        return _last_login_sort_key

    if sort_key == "joined":
        return _date_joined_sort_key

    return _email_sort_key


def _email_sort_key(row: AccountListRow):
    return row.email.casefold()


def _role_sort_key(row: AccountListRow):
    return (
        get_role_rank(row.account_role),
        row.email.casefold(),
    )


def _linked_identity_sort_key(row: AccountListRow):
    return (
        row.linked_identity.casefold(),
        row.email.casefold(),
    )


def _status_sort_key(row: AccountListRow):
    return (
        0 if row.is_active else 1,
        row.email.casefold(),
    )


def _last_login_sort_key(row: AccountListRow):
    return (
        row.last_login or _oldest_datetime(),
        row.email.casefold(),
    )


def _date_joined_sort_key(row: AccountListRow):
    return (
        row.date_joined,
        row.email.casefold(),
    )


def _oldest_datetime() -> datetime:
    return datetime.min.replace(tzinfo=timezone.get_current_timezone())


def _activity_rows_from_specs(
    *,
    user,
    specs: tuple[ActivitySpec, ...],
    use_customer_portal_links: bool = False,
) -> list[AccountActivityRow]:
    rows: list[AccountActivityRow] = []

    for spec in specs:
        queryset = spec.model.objects.filter(
            **{
                spec.actor_field: user,
                f"{spec.occurred_at_field}__isnull": False,
            }
        )

        if spec.select_related:
            queryset = queryset.select_related(*spec.select_related)

        queryset = queryset.order_by(f"-{spec.occurred_at_field}")[
            :ACCOUNT_ACTIVITY_LIMIT
        ]

        rows.extend(
            _activity_row_from_spec(
                item=item,
                spec=spec,
                use_customer_portal_links=use_customer_portal_links,
            )
            for item in queryset
        )

    return rows


def _activity_row_from_spec(
    *,
    item,
    spec: ActivitySpec,
    use_customer_portal_links: bool = False,
) -> AccountActivityRow:
    occurred_at = getattr(item, spec.occurred_at_field)

    return _activity_row(
        occurred_at=occurred_at,
        event_label=spec.event_label,
        target_label=spec.target_label(item),
        target_href=_activity_target_href(
            item=item,
            spec=spec,
            use_customer_portal_links=use_customer_portal_links,
        ),
        meta=spec.meta(item),
        tone=spec.tone,
    )


def _activity_target_href(
    *,
    item,
    spec: ActivitySpec,
    use_customer_portal_links: bool,
) -> str:
    if use_customer_portal_links and isinstance(item, Order):
        return reverse(
            "customer_portal:order_detail",
            kwargs={
                "order_id": item.pk,
            },
        )

    return reverse(
        spec.route_name,
        kwargs={
            spec.route_kwarg: item.pk,
        },
    )


def _activity_row(
    *,
    occurred_at: datetime,
    event_label: str,
    target_label: str,
    target_href: str,
    meta: str,
    tone: str,
) -> AccountActivityRow:
    return AccountActivityRow(
        occurred_at=occurred_at,
        occurred_at_label=_datetime_label(occurred_at),
        event_label=event_label,
        target_label=target_label,
        target_href=target_href,
        meta=meta,
        tone=tone,
    )


# TODO: Consider creating a common utility for formatting datetimes in the local
# timezone, due to the same usage in multiple places across the codebase.
def _datetime_label(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _has_staff_account(user) -> bool:
    return hasattr(user, "staff_account")


def _has_customer_membership(user) -> bool:
    return hasattr(user, "customer_membership")
