"""
Primary navigation for account roles.

Navigation is not authorization.

accounts.policies decides what routes can be reached.
accounts.roles decides what each role can do.
This module decides which links each role should see in the main navigation.

A role may have read access to supporting routes without those routes being
top-level navigation items. For example, restricted staff may be able to open a
customer detail page from an order, while not seeing Customers as a main nav
link.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import AccountRole, Capability, RoleSpec


@dataclass(frozen=True, slots=True)
class NavItem:
    """A single link in the primary navigation."""

    label: str
    route_name: str
    namespace: str
    icon: str
    capability: Capability

    @property
    def href(self) -> str:
        return reverse(self.route_name)


# -----------------------------------------------------------------------------
# Available navigation items.
#
# Add new primary navigation links here. Visibility is still filtered by
# capability, but each role chooses from its own nav item set below.


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

CATALOG_NAV_ITEM = NavItem(
    label="Catalog",
    route_name="products:index",
    namespace="products",
    icon="lollipop",
    capability=Capability.VIEW_OPS_PRODUCTS,
)


# -----------------------------------------------------------------------------
# Role-specific primary navigation.
#
# This is UX, not authorization. A role can have access to a route without that
# route appearing as a top-level nav item.


STAFF_NAV_ITEMS = (
    CUSTOMERS_NAV_ITEM,
    ORDERS_NAV_ITEM,
    INVENTORY_NAV_ITEM,
    CATALOG_NAV_ITEM,
)

RESTRICTED_STAFF_NAV_ITEMS = (
    ORDERS_NAV_ITEM,
    INVENTORY_NAV_ITEM,
)

CUSTOMER_NAV_ITEMS: tuple[NavItem, ...] = ()


NAV_ITEMS_BY_ROLE: dict[AccountRole, tuple[NavItem, ...]] = {
    AccountRole.OWNER: STAFF_NAV_ITEMS,
    AccountRole.FULL_STAFF: STAFF_NAV_ITEMS,
    AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_NAV_ITEMS,
    AccountRole.CUSTOMER: CUSTOMER_NAV_ITEMS,
}


def build_primary_nav_items(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> tuple[NavItem, ...]:
    candidates = NAV_ITEMS_BY_ROLE.get(account_role, ())

    return _filter_nav_items(
        candidates=candidates,
        role_spec=role_spec,
    )


def _filter_nav_items(
    *,
    candidates: tuple[NavItem, ...],
    role_spec: RoleSpec,
) -> tuple[NavItem, ...]:
    return tuple(
        item
        for item in candidates
        if role_spec.allows(item.capability)
    )
