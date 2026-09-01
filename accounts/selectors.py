from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role
from accounts.roles import AccountRole, StaffAccessLevel, get_role_rank
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


class AccountIdentityKind(StrEnum):
    OWNER = "owner"
    STAFF = "staff"
    BUSINESS_CUSTOMER = "business_customer"
    INVALID_STAFF_AND_CUSTOMER = "invalid_staff_and_customer"
    INVALID_STAFF = "invalid_staff"
    INVALID_CUSTOMER = "invalid_customer"
    UNLINKED = "unlinked"


class AccountActivityKind(StrEnum):
    ORDER_PLACED = "order_placed"
    ORDER_PACKED = "order_packed"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_EDITED = "order_edited"

    PRODUCT_CREATED = "product_created"
    PRODUCT_EDITED = "product_edited"
    PRODUCT_ACTIVATED = "product_activated"
    PRODUCT_DEACTIVATED = "product_deactivated"

    INVENTORY_ADDED = "inventory_added"
    INVENTORY_EDITED = "inventory_edited"
    INVENTORY_CLOSED = "inventory_closed"

    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_EDITED = "customer_edited"
    CUSTOMER_ACTIVATED = "customer_activated"
    CUSTOMER_DEACTIVATED = "customer_deactivated"


@dataclass(frozen=True, slots=True)
class AccountIdentity:
    kind: AccountIdentityKind
    customer_id: int | None = None
    customer_name: str = ""
    staff_access_level: StaffAccessLevel | str | None = None


@dataclass(frozen=True, slots=True)
class AccountRecord:
    user_id: int
    email: str
    account_role: AccountRole
    identity: AccountIdentity
    is_active: bool
    last_login: datetime | None
    date_joined: datetime


@dataclass(frozen=True, slots=True)
class AccountActivity:
    occurred_at: datetime
    kind: AccountActivityKind
    target: object


@dataclass(frozen=True, slots=True)
class ActivitySpec:
    model: type
    actor_field: str
    occurred_at_field: str
    kind: AccountActivityKind
    select_related: tuple[str, ...] = ()


ORDER_ACTIVITY_SPECS = (
    ActivitySpec(
        model=Order,
        actor_field="placed_by",
        occurred_at_field="placed_at",
        kind=AccountActivityKind.ORDER_PLACED,
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="packed_by",
        occurred_at_field="packed_at",
        kind=AccountActivityKind.ORDER_PACKED,
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="delivered_by",
        occurred_at_field="delivered_at",
        kind=AccountActivityKind.ORDER_DELIVERED,
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="cancelled_by",
        occurred_at_field="cancelled_at",
        kind=AccountActivityKind.ORDER_CANCELLED,
        select_related=("customer",),
    ),
    ActivitySpec(
        model=Order,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        kind=AccountActivityKind.ORDER_EDITED,
        select_related=("customer",),
    ),
)


PRODUCT_ACTIVITY_SPECS = (
    ActivitySpec(
        model=Product,
        actor_field="created_by",
        occurred_at_field="created_at",
        kind=AccountActivityKind.PRODUCT_CREATED,
    ),
    ActivitySpec(
        model=Product,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        kind=AccountActivityKind.PRODUCT_EDITED,
    ),
    ActivitySpec(
        model=Product,
        actor_field="activated_by",
        occurred_at_field="activated_at",
        kind=AccountActivityKind.PRODUCT_ACTIVATED,
    ),
    ActivitySpec(
        model=Product,
        actor_field="deactivated_by",
        occurred_at_field="deactivated_at",
        kind=AccountActivityKind.PRODUCT_DEACTIVATED,
    ),
)


INVENTORY_ACTIVITY_SPECS = (
    ActivitySpec(
        model=InventoryBatch,
        actor_field="created_by",
        occurred_at_field="created_at",
        kind=AccountActivityKind.INVENTORY_ADDED,
        select_related=("product",),
    ),
    ActivitySpec(
        model=InventoryBatch,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        kind=AccountActivityKind.INVENTORY_EDITED,
        select_related=("product",),
    ),
    ActivitySpec(
        model=InventoryBatch,
        actor_field="closed_by",
        occurred_at_field="closed_at",
        kind=AccountActivityKind.INVENTORY_CLOSED,
        select_related=("product",),
    ),
)


CUSTOMER_ACTIVITY_SPECS = (
    ActivitySpec(
        model=Customer,
        actor_field="created_by",
        occurred_at_field="created_at",
        kind=AccountActivityKind.CUSTOMER_CREATED,
    ),
    ActivitySpec(
        model=Customer,
        actor_field="edited_by",
        occurred_at_field="edited_at",
        kind=AccountActivityKind.CUSTOMER_EDITED,
    ),
    ActivitySpec(
        model=Customer,
        actor_field="activated_by",
        occurred_at_field="activated_at",
        kind=AccountActivityKind.CUSTOMER_ACTIVATED,
    ),
    ActivitySpec(
        model=Customer,
        actor_field="deactivated_by",
        occurred_at_field="deactivated_at",
        kind=AccountActivityKind.CUSTOMER_DEACTIVATED,
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


def get_account_record(*, user) -> AccountRecord:
    return _build_account_record(user)


def list_internal_account_records(*, sort: str) -> tuple[AccountRecord, ...]:
    return _list_account_records_for_roles(
        roles=INTERNAL_ACCOUNT_ROLES,
        sort=sort,
    )


def list_business_customer_account_records(
    *,
    sort: str,
) -> tuple[AccountRecord, ...]:
    return _list_account_records_for_roles(
        roles=frozenset({AccountRole.BUSINESS_CUSTOMER}),
        sort=sort,
    )


def list_unlinked_account_records(*, sort: str) -> tuple[AccountRecord, ...]:
    return _list_account_records_for_roles(
        roles=frozenset({AccountRole.UNKNOWN}),
        sort=sort,
    )


def list_account_activities(*, user) -> tuple[AccountActivity, ...]:
    activities = _activities_from_specs(
        user=user,
        specs=ACCOUNT_ACTIVITY_SPECS,
    )

    return tuple(
        sorted(
            activities,
            key=lambda activity: activity.occurred_at,
            reverse=True,
        )[:ACCOUNT_ACTIVITY_LIMIT]
    )


def _list_account_records_for_roles(
    *,
    roles: frozenset[AccountRole],
    sort: str,
) -> tuple[AccountRecord, ...]:
    records = tuple(
        record
        for record in _list_all_account_records()
        if record.account_role in roles
    )

    return _sort_account_records(
        records=records,
        sort=sort,
    )


def _list_all_account_records() -> tuple[AccountRecord, ...]:
    users = User.objects.select_related(
        "staff_account",
        "customer_membership__customer",
    ).order_by(
        "email",
        "username",
    )

    return tuple(
        _build_account_record(user)
        for user in users
    )


def _build_account_record(user) -> AccountRecord:
    return AccountRecord(
        user_id=user.pk,
        email=user.email or user.username,
        account_role=_resolve_safe_account_role(user),
        identity=_resolve_account_identity(user),
        is_active=user.is_active,
        last_login=user.last_login,
        date_joined=user.date_joined,
    )


def _resolve_account_identity(user) -> AccountIdentity:
    account_role = _resolve_safe_account_role(user)
    has_staff_account = _has_staff_account(user)
    has_customer_membership = _has_customer_membership(user)

    if account_role == AccountRole.OWNER:
        return AccountIdentity(
            kind=AccountIdentityKind.OWNER,
        )

    if has_staff_account and has_customer_membership:
        customer = user.customer_membership.customer

        return AccountIdentity(
            kind=AccountIdentityKind.INVALID_STAFF_AND_CUSTOMER,
            customer_id=customer.pk,
            customer_name=customer.name,
            staff_access_level=user.staff_account.access_level,
        )

    if account_role in {
        AccountRole.FULL_STAFF,
        AccountRole.RESTRICTED_STAFF,
    }:
        return AccountIdentity(
            kind=AccountIdentityKind.STAFF,
            staff_access_level=user.staff_account.access_level,
        )

    if account_role == AccountRole.BUSINESS_CUSTOMER:
        customer = user.customer_membership.customer

        return AccountIdentity(
            kind=AccountIdentityKind.BUSINESS_CUSTOMER,
            customer_id=customer.pk,
            customer_name=customer.name,
        )

    if has_staff_account:
        return AccountIdentity(
            kind=AccountIdentityKind.INVALID_STAFF,
            staff_access_level=user.staff_account.access_level,
        )

    if has_customer_membership:
        customer = user.customer_membership.customer

        return AccountIdentity(
            kind=AccountIdentityKind.INVALID_CUSTOMER,
            customer_id=customer.pk,
            customer_name=customer.name,
        )

    return AccountIdentity(
        kind=AccountIdentityKind.UNLINKED,
    )


def _resolve_safe_account_role(user) -> AccountRole:
    try:
        return resolve_account_role(user)
    except InvalidAccountIdentity:
        return AccountRole.UNKNOWN


def _sort_account_records(
    *,
    records: tuple[AccountRecord, ...],
    sort: str,
) -> tuple[AccountRecord, ...]:
    reverse = sort.startswith("-")
    sort_key = sort.removeprefix("-")

    return tuple(
        sorted(
            records,
            key=_account_sort_key(sort_key),
            reverse=reverse,
        )
    )


def _account_sort_key(sort_key: str):
    sort_keys = {
        "role": _role_sort_key,
        "linked": _linked_identity_sort_key,
        "status": _status_sort_key,
        "last_login": _last_login_sort_key,
        "joined": _date_joined_sort_key,
    }

    return sort_keys.get(
        sort_key,
        _email_sort_key,
    )


def _email_sort_key(record: AccountRecord):
    return record.email.casefold()


def _role_sort_key(record: AccountRecord):
    return (
        get_role_rank(record.account_role),
        record.email.casefold(),
    )


def _linked_identity_sort_key(record: AccountRecord):
    identity = record.identity

    return (
        identity.customer_name.casefold(),
        str(identity.staff_access_level or "").casefold(),
        identity.kind.value,
        record.email.casefold(),
    )


def _status_sort_key(record: AccountRecord):
    return (
        0 if record.is_active else 1,
        record.email.casefold(),
    )


def _last_login_sort_key(record: AccountRecord):
    return (
        record.last_login or _oldest_datetime(),
        record.email.casefold(),
    )


def _date_joined_sort_key(record: AccountRecord):
    return (
        record.date_joined,
        record.email.casefold(),
    )


def _oldest_datetime() -> datetime:
    return datetime.min.replace(
        tzinfo=timezone.get_current_timezone()
    )


def _activities_from_specs(
    *,
    user,
    specs: tuple[ActivitySpec, ...],
) -> list[AccountActivity]:
    activities: list[AccountActivity] = []

    for spec in specs:
        queryset = spec.model.objects.filter(
            **{
                spec.actor_field: user,
                f"{spec.occurred_at_field}__isnull": False,
            }
        )

        if spec.select_related:
            queryset = queryset.select_related(
                *spec.select_related
            )

        queryset = queryset.order_by(
            f"-{spec.occurred_at_field}"
        )[:ACCOUNT_ACTIVITY_LIMIT]

        activities.extend(
            AccountActivity(
                occurred_at=getattr(
                    item,
                    spec.occurred_at_field,
                ),
                kind=spec.kind,
                target=item,
            )
            for item in queryset
        )

    return activities


def _has_staff_account(user) -> bool:
    return hasattr(
        user,
        "staff_account",
    )


def _has_customer_membership(user) -> bool:
    return hasattr(
        user,
        "customer_membership",
    )
