from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True, slots=True)
class NavItem:
    label: str
    href: str
    namespace: str
    icon: str
    capability: str


def build_primary_nav_items(*, role_spec) -> tuple[NavItem, ...]:
    candidates = (
        NavItem(
            label="Customers",
            href=reverse("customers:index"),
            namespace="customers",
            icon="users",
            capability="can_view_customers",
        ),
        NavItem(
            label="Orders",
            href=reverse("orders:index"),
            namespace="orders",
            icon="cart",
            capability="can_view_orders",
        ),
        NavItem(
            label="Inventory",
            href=reverse("inventory:index"),
            namespace="inventory",
            icon="inventory",
            capability="can_view_inventory",
        ),
        NavItem(
            label="Catalog",
            href=reverse("products:index"),
            namespace="products",
            icon="lollipop",
            capability="can_view_ops_products",
        ),
    )

    return tuple(
        item
        for item in candidates
        if getattr(role_spec, item.capability, False)
    )
