from __future__ import annotations

from accounts.navigation import build_primary_nav_items
from accounts.roles import (
    FULL_STAFF_SPEC,
    OWNER_SPEC,
    RESTRICTED_STAFF_SPEC,
    UNKNOWN_SPEC,
    AccountRole,
)


def _labels(items):
    return tuple(item.label for item in items)


def test_owner_sees_full_staff_navigation():
    items = build_primary_nav_items(
        account_role=AccountRole.OWNER,
        role_spec=OWNER_SPEC,
    )

    assert _labels(items) == (
        "Customers",
        "Orders",
        "Inventory",
        "Products",
        "Accounts",
    )


def test_full_staff_sees_full_staff_navigation():
    items = build_primary_nav_items(
        account_role=AccountRole.FULL_STAFF,
        role_spec=FULL_STAFF_SPEC,
    )

    assert _labels(items) == (
        "Customers",
        "Orders",
        "Inventory",
        "Products",
        "Accounts",
    )


def test_restricted_staff_sees_restricted_navigation():
    items = build_primary_nav_items(
        account_role=AccountRole.RESTRICTED_STAFF,
        role_spec=RESTRICTED_STAFF_SPEC,
    )

    assert _labels(items) == (
        "Orders",
        "Inventory",
    )


def test_unknown_user_sees_no_navigation():
    items = build_primary_nav_items(
        account_role=AccountRole.UNKNOWN,
        role_spec=UNKNOWN_SPEC,
    )

    assert items == ()
