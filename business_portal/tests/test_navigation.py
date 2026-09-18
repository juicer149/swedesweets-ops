from django.urls import reverse

from business_portal.navigation import (
    build_business_primary_nav_items,
)


def test_business_navigation_has_shared_site_shape():
    items = build_business_primary_nav_items()

    assert tuple(
        item.label
        for item in items
    ) == (
        "Catalog",
        "Contact",
        "FAQ",
    )


def test_business_catalog_uses_business_sales_channel():
    items = build_business_primary_nav_items()

    catalog_item = items[0]

    assert (
        catalog_item.route_name
        == "business_portal:catalog"
    )
    assert (
        catalog_item.href
        == reverse("business_portal:catalog")
    )


def test_business_contact_and_faq_stay_in_business_portal():
    items = build_business_primary_nav_items()

    contact_item = items[1]
    faq_item = items[2]

    assert (
        contact_item.route_name
        == "business_portal:contact"
    )
    assert (
        contact_item.href
        == reverse("business_portal:contact")
    )

    assert (
        faq_item.route_name
        == "business_portal:faq"
    )
    assert (
        faq_item.href
        == reverse("business_portal:faq")
    )


def test_business_navigation_does_not_include_account_pages():
    items = build_business_primary_nav_items()

    route_names = {
        item.route_name
        for item in items
    }

    assert "business_portal:profile" not in route_names
    assert "business_portal:orders" not in route_names
