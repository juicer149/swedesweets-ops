from __future__ import annotations

from accounts.roles import BUSINESS_CUSTOMER_SPEC
from business_portal.navigation import build_business_primary_nav_items


def _labels(items):
    return tuple(item.label for item in items)


def _route_names(items):
    return tuple(item.route_name for item in items)


def test_business_customer_sees_business_portal_navigation():
    items = build_business_primary_nav_items(
        role_spec=BUSINESS_CUSTOMER_SPEC,
    )

    assert _labels(items) == (
        "Orders",
        "Store profile",
        "Contact",
    )


def test_business_navigation_uses_business_portal_routes():
    items = build_business_primary_nav_items(
        role_spec=BUSINESS_CUSTOMER_SPEC,
    )

    assert _route_names(items) == (
        "business_portal:orders",
        "business_portal:profile",
        "business_portal:contact",
    )
