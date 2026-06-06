from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role
from accounts.roles import AccountRole, StaffAccessLevel


User = get_user_model()


INTERNAL_ACCOUNT_ROLES = frozenset(
    {
        AccountRole.OWNER,
        AccountRole.FULL_STAFF,
        AccountRole.RESTRICTED_STAFF,
    }
)


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


def _has_staff_account(user) -> bool:
    return hasattr(user, "staff_account")


def _has_customer_membership(user) -> bool:
    return hasattr(user, "customer_membership")
