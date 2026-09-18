from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True, slots=True)
class BusinessNavItem:
    """A primary navigation link for the business sales channel."""

    label: str
    route_name: str
    namespace: str
    icon: str = ""
    active_url_names: tuple[str, ...] = ()

    @property
    def href(self) -> str:
        return reverse(self.route_name)


BUSINESS_CATALOG_NAV_ITEM = BusinessNavItem(
    label=_("Catalog"),
    route_name="business_portal:catalog",
    namespace="business_portal",
    icon="lollipop",
    active_url_names=(
        "catalog",
        "catalog_product",
    ),
)

BUSINESS_CONTACT_NAV_ITEM = BusinessNavItem(
    label=_("Contact"),
    route_name="business_portal:contact",
    namespace="business_portal",
    icon="mail",
    active_url_names=("contact",),
)

BUSINESS_FAQ_NAV_ITEM = BusinessNavItem(
    label=_("FAQ"),
    route_name="business_portal:faq",
    namespace="business_portal",
    icon="",
    active_url_names=("faq",),
)


BUSINESS_PRIMARY_NAV_ITEMS = (
    BUSINESS_CATALOG_NAV_ITEM,
    BUSINESS_CONTACT_NAV_ITEM,
    BUSINESS_FAQ_NAV_ITEM,
)


def build_business_primary_nav_items() -> tuple[BusinessNavItem, ...]:
    return BUSINESS_PRIMARY_NAV_ITEMS
