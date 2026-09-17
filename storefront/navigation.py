"""
Navigation for the public storefront.

The storefront's link row is identical for every visitor - anonymous,
business customer or staff - so these items carry no capability and are
never filtered. What varies by identity is the account slot, not the
chrome.

Site chrome, sales channel and identity are separate concerns:

    chrome   - Shop / Contact / FAQ, same for everyone
    channel  - which catalog and cart the links resolve to
    identity - what the account slot offers

This module owns the first two for the retail channel. Identity menus are
built in accounts_menu.py so the same account slot can be filled by any
zone.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True, slots=True)
class PublicNavItem:
    """A storefront link.

    Deliberately not common.navigation.NavItem: that type requires a
    Capability, and every storefront link is visible to everyone. Adding a
    Capability here just to satisfy the type would put a permission on
    something that has no permission.
    """

    label: str
    route_name: str
    namespace: str
    icon: str = ""
    active_url_names: tuple[str, ...] = ()

    @property
    def href(self) -> str:
        return reverse(self.route_name)


STOREFRONT_CATALOG_NAV_ITEM = PublicNavItem(
    label=_("Shop"),
    route_name="storefront:product_list",
    namespace="storefront",
    icon="lollipop",
    active_url_names=(
        "product_list",
        "product_detail",
    ),
)

STOREFRONT_CONTACT_NAV_ITEM = PublicNavItem(
    label=_("Contact"),
    route_name="storefront:contact",
    namespace="storefront",
    icon="mail",
    active_url_names=("contact",),
)

STOREFRONT_FAQ_NAV_ITEM = PublicNavItem(
    label=_("FAQ"),
    route_name="storefront:faq",
    namespace="storefront",
    # No question-mark icon exists in includes/ui/icon.html yet. The
    # navbar renders the label alone when icon is empty, so this stays
    # blank rather than borrowing a misleading one.
    icon="",
    active_url_names=("faq",),
)


PUBLIC_PRIMARY_NAV_ITEMS = (
    STOREFRONT_CATALOG_NAV_ITEM,
    STOREFRONT_CONTACT_NAV_ITEM,
    STOREFRONT_FAQ_NAV_ITEM,
)


def build_public_primary_nav_items() -> tuple[PublicNavItem, ...]:
    return PUBLIC_PRIMARY_NAV_ITEMS
