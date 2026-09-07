from __future__ import annotations

from django.urls import resolve, reverse

from business_portal.catalog import views


def test_business_catalog_route_points_to_catalog_view():
    match = resolve(
        reverse("business_portal:catalog")
    )

    assert match.func == views.catalog
