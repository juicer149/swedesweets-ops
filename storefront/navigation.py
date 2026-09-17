"""
Navigation for the public storefront.

The public site chrome is shared by retail visitors, business customers and
staff. The commerce destination varies by sales channel, while Contact and
FAQ are shared public-site resources.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True, slots=True)
class PublicNavItem:
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
    route_name="public_site:contact",
    namespace="public_site",
    icon="mail",
    active_url_names=("contact",),
)

STOREFRONT_FAQ_NAV_ITEM = PublicNavItem(
    label=_("FAQ"),
    route_name="public_site:faq",
    namespace="public_site",
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
