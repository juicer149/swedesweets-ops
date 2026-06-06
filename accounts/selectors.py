from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role
from accounts.roles import AccountRole, StaffAccessLevel
from customers.models import Customer
from inventory.models import InventoryBatch
from orders.models import Order
from products.models import Product


# TODO rensa och flytta många queries till rätt appar etc

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
    rows = tuple(
        row
        for row in _list_all_account_rows()
        if row.account_role in INTERNAL_ACCOUNT_ROLES
    )

    return _sort_account_rows(rows=rows, sort=sort)


def list_customer_account_rows(*, sort: str) -> tuple[AccountListRow, ...]:
    rows = tuple(
        row
        for row in _list_all_account_rows()
        if row.account_role == AccountRole.CUSTOMER
    )

    return _sort_account_rows(rows=rows, sort=sort)


def list_unlinked_account_rows(*, sort: str) -> tuple[AccountListRow, ...]:
    rows = tuple(
        row
        for row in _list_all_account_rows()
        if row.account_role == AccountRole.UNKNOWN
    )

    return _sort_account_rows(rows=rows, sort=sort)


def list_account_activity_rows(*, user) -> tuple[AccountActivityRow, ...]:
    rows: list[AccountActivityRow] = []

    rows.extend(_order_activity_rows(user=user))
    rows.extend(_product_activity_rows(user=user))
    rows.extend(_inventory_activity_rows(user=user))
    rows.extend(_customer_activity_rows(user=user))

    return tuple(
        sorted(
            rows,
            key=lambda row: row.occurred_at,
            reverse=True,
        )[:ACCOUNT_ACTIVITY_LIMIT]
    )


def _list_all_account_rows() -> tuple[AccountListRow, ...]:
    users = (
        User.objects
        .select_related(
            "staff_account",
            "customer_membership__customer",
        )
        .order_by("email", "username")
    )

    return tuple(
        _build_account_row(user)
        for user in users
    )


def _build_account_row(user) -> AccountListRow:
    account_role = _resolve_safe_account_role(user)

    return AccountListRow(
        user_id=user.pk,
        email=user.email or user.username,
        account_role=account_role,
        role_label=_role_label(
            user=user,
            account_role=account_role,
        ),
        linked_identity=_linked_identity(user=user),
        status_label=_status_label(user=user),
        is_active=user.is_active,
        last_login=user.last_login,
        date_joined=user.date_joined,
    )


def _resolve_safe_account_role(user) -> AccountRole:
    try:
        return resolve_account_role(user)
    except InvalidAccountIdentity:
        return AccountRole.UNKNOWN


def _role_label(
    *,
    user,
    account_role: AccountRole,
) -> str:
    if account_role == AccountRole.OWNER:
        return "Owner"

    if account_role == AccountRole.FULL_STAFF:
        return "Full staff"

    if account_role == AccountRole.RESTRICTED_STAFF:
        return "Restricted staff"

    if account_role == AccountRole.CUSTOMER:
        return "Customer"

    if _has_staff_account(user) and _has_customer_membership(user):
        return "Invalid identity"

    if _has_staff_account(user):
        return "Invalid staff account"

    if _has_customer_membership(user):
        return "Invalid customer account"

    return "Unlinked"


def _linked_identity(*, user) -> str:
    if _has_staff_account(user):
        return _staff_identity_label(user.staff_account.access_level)

    if _has_customer_membership(user):
        return user.customer_membership.customer.name

    if user.is_superuser:
        return "Superuser"

    return "—"


def _staff_identity_label(access_level: str) -> str:
    if access_level == StaffAccessLevel.FULL:
        return "Internal staff · Full access"

    if access_level == StaffAccessLevel.RESTRICTED:
        return "Internal staff · Restricted access"

    return "Internal staff"


def _status_label(*, user) -> str:
    if user.is_active:
        return "Active"

    return "Inactive"


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
        _role_rank(row.account_role),
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


def _role_rank(account_role: AccountRole) -> int:
    ranks = {
        AccountRole.OWNER: 0,
        AccountRole.FULL_STAFF: 1,
        AccountRole.RESTRICTED_STAFF: 2,
        AccountRole.CUSTOMER: 3,
        AccountRole.UNKNOWN: 4,
    }

    return ranks.get(account_role, 99)


def _oldest_datetime() -> datetime:
    return datetime.min.replace(tzinfo=timezone.get_current_timezone())


def _order_activity_rows(*, user) -> list[AccountActivityRow]:
    rows: list[AccountActivityRow] = []

    orders = (
        Order.objects
        .filter(
            placed_by=user,
        )
        .select_related("customer")
        .order_by("-placed_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=order.placed_at,
            event_label="Placed order",
            target_label=f"Order #{order.pk}",
            target_href=reverse("orders:detail", kwargs={"order_id": order.pk}),
            meta=order.customer_name,
            tone="success",
        )
        for order in orders
        if order.placed_at is not None
    )

    orders = (
        Order.objects
        .filter(
            packed_by=user,
        )
        .select_related("customer")
        .order_by("-packed_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=order.packed_at,
            event_label="Packed order",
            target_label=f"Order #{order.pk}",
            target_href=reverse("orders:detail", kwargs={"order_id": order.pk}),
            meta=order.customer_name,
            tone="info",
        )
        for order in orders
        if order.packed_at is not None
    )

    orders = (
        Order.objects
        .filter(
            delivered_by=user,
        )
        .select_related("customer")
        .order_by("-delivered_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=order.delivered_at,
            event_label="Delivered order",
            target_label=f"Order #{order.pk}",
            target_href=reverse("orders:detail", kwargs={"order_id": order.pk}),
            meta=order.customer_name,
            tone="success",
        )
        for order in orders
        if order.delivered_at is not None
    )

    orders = (
        Order.objects
        .filter(
            cancelled_by=user,
        )
        .select_related("customer")
        .order_by("-cancelled_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=order.cancelled_at,
            event_label="Cancelled order",
            target_label=f"Order #{order.pk}",
            target_href=reverse("orders:detail", kwargs={"order_id": order.pk}),
            meta=order.customer_name,
            tone="danger",
        )
        for order in orders
        if order.cancelled_at is not None
    )

    orders = (
        Order.objects
        .filter(
            edited_by=user,
        )
        .select_related("customer")
        .order_by("-edited_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=order.edited_at,
            event_label="Edited order",
            target_label=f"Order #{order.pk}",
            target_href=reverse("orders:detail", kwargs={"order_id": order.pk}),
            meta=order.customer_name,
            tone="neutral",
        )
        for order in orders
        if order.edited_at is not None
    )

    return rows


def _product_activity_rows(*, user) -> list[AccountActivityRow]:
    rows: list[AccountActivityRow] = []

    products = (
        Product.objects
        .filter(created_by=user)
        .order_by("-created_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=product.created_at,
            event_label="Created product",
            target_label=product.display_name,
            target_href=reverse("products:detail", kwargs={"product_pk": product.pk}),
            meta=product.code_label,
            tone="success",
        )
        for product in products
    )

    products = (
        Product.objects
        .filter(edited_by=user)
        .order_by("-edited_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=product.edited_at,
            event_label="Edited product",
            target_label=product.display_name,
            target_href=reverse("products:detail", kwargs={"product_pk": product.pk}),
            meta=product.code_label,
            tone="neutral",
        )
        for product in products
        if product.edited_at is not None
    )

    products = (
        Product.objects
        .filter(activated_by=user)
        .order_by("-activated_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=product.activated_at,
            event_label="Activated product",
            target_label=product.display_name,
            target_href=reverse("products:detail", kwargs={"product_pk": product.pk}),
            meta=product.code_label,
            tone="success",
        )
        for product in products
        if product.activated_at is not None
    )

    products = (
        Product.objects
        .filter(deactivated_by=user)
        .order_by("-deactivated_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=product.deactivated_at,
            event_label="Deactivated product",
            target_label=product.display_name,
            target_href=reverse("products:detail", kwargs={"product_pk": product.pk}),
            meta=product.code_label,
            tone="muted",
        )
        for product in products
        if product.deactivated_at is not None
    )

    return rows


def _inventory_activity_rows(*, user) -> list[AccountActivityRow]:
    rows: list[AccountActivityRow] = []

    batches = (
        InventoryBatch.objects
        .filter(created_by=user)
        .select_related("product")
        .order_by("-created_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=batch.created_at,
            event_label="Added batch",
            target_label=batch.batch_id,
            target_href=reverse("inventory:detail", kwargs={"batch_pk": batch.pk}),
            meta=batch.product.display_name,
            tone="success",
        )
        for batch in batches
    )

    batches = (
        InventoryBatch.objects
        .filter(edited_by=user)
        .select_related("product")
        .order_by("-edited_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=batch.edited_at,
            event_label="Edited batch",
            target_label=batch.batch_id,
            target_href=reverse("inventory:detail", kwargs={"batch_pk": batch.pk}),
            meta=batch.product.display_name,
            tone="neutral",
        )
        for batch in batches
        if batch.edited_at is not None
    )

    batches = (
        InventoryBatch.objects
        .filter(closed_by=user)
        .select_related("product")
        .order_by("-closed_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=batch.closed_at,
            event_label="Closed batch",
            target_label=batch.batch_id,
            target_href=reverse("inventory:detail", kwargs={"batch_pk": batch.pk}),
            meta=batch.product.display_name,
            tone="muted",
        )
        for batch in batches
        if batch.closed_at is not None
    )

    return rows


def _customer_activity_rows(*, user) -> list[AccountActivityRow]:
    rows: list[AccountActivityRow] = []

    customers = (
        Customer.objects
        .filter(created_by=user)
        .order_by("-created_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=customer.created_at,
            event_label="Created customer",
            target_label=customer.name,
            target_href=reverse("customers:detail", kwargs={"customer_pk": customer.pk}),
            meta=customer.email,
            tone="success",
        )
        for customer in customers
    )

    customers = (
        Customer.objects
        .filter(edited_by=user)
        .order_by("-edited_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=customer.edited_at,
            event_label="Edited customer",
            target_label=customer.name,
            target_href=reverse("customers:detail", kwargs={"customer_pk": customer.pk}),
            meta=customer.email,
            tone="neutral",
        )
        for customer in customers
        if customer.edited_at is not None
    )

    customers = (
        Customer.objects
        .filter(activated_by=user)
        .order_by("-activated_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=customer.activated_at,
            event_label="Activated customer",
            target_label=customer.name,
            target_href=reverse("customers:detail", kwargs={"customer_pk": customer.pk}),
            meta=customer.email,
            tone="success",
        )
        for customer in customers
        if customer.activated_at is not None
    )

    customers = (
        Customer.objects
        .filter(deactivated_by=user)
        .order_by("-deactivated_at")[:ACCOUNT_ACTIVITY_LIMIT]
    )
    rows.extend(
        _activity_row(
            occurred_at=customer.deactivated_at,
            event_label="Deactivated customer",
            target_label=customer.name,
            target_href=reverse("customers:detail", kwargs={"customer_pk": customer.pk}),
            meta=customer.email,
            tone="muted",
        )
        for customer in customers
        if customer.deactivated_at is not None
    )

    return rows


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


def _datetime_label(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _has_staff_account(user) -> bool:
    return hasattr(user, "staff_account")


def _has_customer_membership(user) -> bool:
    return hasattr(user, "customer_membership")
