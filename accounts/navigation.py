"""
Primary navigation for internal account roles.

Navigation is not authorization.

accounts.policies decides what routes can be reached.
accounts.roles decides what each role can do.
This module defines internal staff navigation only.
"""

from __future__ import annotations

from django.urls import reverse

from accounts.roles import AccountRole, Capability, RoleSpec
from common.navigation import NavItem, filter_nav_items


CUSTOMERS_NAV_ITEM = NavItem(
    label="Customers",
    route_name="customers:index",
    namespace="customers",
    icon="users",
    capability=Capability.VIEW_CUSTOMERS,
)

ORDERS_NAV_ITEM = NavItem(
    label="Orders",
    route_name="orders:index",
    namespace="orders",
    icon="cart",
    capability=Capability.VIEW_ORDERS,
)

INVENTORY_NAV_ITEM = NavItem(
    label="Inventory",
    route_name="inventory:index",
    namespace="inventory",
    icon="inventory",
    capability=Capability.VIEW_INVENTORY,
)

PRODUCTS_NAV_ITEM = NavItem(
    label="Products",
    route_name="products:index",
    namespace="products",
    icon="lollipop",
    capability=Capability.VIEW_OPS_PRODUCTS,
)

ACCOUNTS_NAV_ITEM = NavItem(
    label="Accounts",
    route_name="accounts:index",
    namespace="accounts",
    icon="users",
    capability=Capability.MANAGE_ACCOUNTS,
)


STAFF_NAV_ITEMS = (
    CUSTOMERS_NAV_ITEM,
    ORDERS_NAV_ITEM,
    INVENTORY_NAV_ITEM,
    PRODUCTS_NAV_ITEM,
    ACCOUNTS_NAV_ITEM,
)

RESTRICTED_STAFF_NAV_ITEMS = (
    ORDERS_NAV_ITEM,
    INVENTORY_NAV_ITEM,
)


NAV_ITEMS_BY_ROLE: dict[AccountRole, tuple[NavItem, ...]] = {
    AccountRole.OWNER: STAFF_NAV_ITEMS,
    AccountRole.FULL_STAFF: STAFF_NAV_ITEMS,
    AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_NAV_ITEMS,
}


def build_staff_primary_nav_items(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> tuple[NavItem, ...]:
    candidates = NAV_ITEMS_BY_ROLE.get(account_role, ())

    return filter_nav_items(
        candidates=candidates,
        role_spec=role_spec,
    )


def build_home_href(
    *,
    account_role: AccountRole | None,
    role_spec: RoleSpec | None,
) -> str:
    if account_role is None or role_spec is None:
        return reverse("login")

    return reverse("accounts:after_login")
