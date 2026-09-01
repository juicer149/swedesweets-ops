from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from accounts.roles import Capability, RoleSpec
from common.navigation import NavItem, filter_nav_items


BUSINESS_ORDERS_NAV_ITEM = NavItem(
    label=_("Orders"),
    route_name="business_portal:orders",
    namespace="business_portal",
    icon="packed",
    capability=Capability.VIEW_OWN_ORDERS,
    active_url_names=("orders", "order_detail"),
)

BUSINESS_CATALOG_NAV_ITEM = NavItem(
    label=_("Catalog"),
    route_name="business_portal:catalog",
    namespace="business_portal",
    icon="lollipop",
    capability=Capability.VIEW_BUSINESS_PORTAL,
    active_url_names=("catalog",),
)

BUSINESS_PROFILE_NAV_ITEM = NavItem(
    label=_("Store profile"),
    route_name="business_portal:profile",
    namespace="business_portal",
    icon="users",
    capability=Capability.VIEW_OWN_ACCOUNT,
    active_url_names=("profile", "edit_profile"),
)

BUSINESS_CONTACT_NAV_ITEM = NavItem(
    label=_("Contact"),
    route_name="business_portal:contact",
    namespace="business_portal",
    icon="tag",
    capability=Capability.VIEW_BUSINESS_PORTAL,
    active_url_names=("contact",),
)


BUSINESS_PRIMARY_NAV_ITEMS = (
    BUSINESS_ORDERS_NAV_ITEM,
    # Add this back when the business catalog is implemented.
    # BUSINESS_CATALOG_NAV_ITEM,
    BUSINESS_PROFILE_NAV_ITEM,
    BUSINESS_CONTACT_NAV_ITEM,
)


def build_business_primary_nav_items(
    *,
    role_spec: RoleSpec,
) -> tuple[NavItem, ...]:
    return filter_nav_items(
        candidates=BUSINESS_PRIMARY_NAV_ITEMS,
        role_spec=role_spec,
    )
