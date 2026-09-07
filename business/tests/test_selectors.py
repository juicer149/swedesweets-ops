from __future__ import annotations

import pytest

from business.selectors import (
    list_business_catalog_entries,
)
from products.models import Product


def _product(
    *,
    internal_number: int,
    name: str,
    active: bool = True,
) -> Product:
    return Product.objects.create(
        internal_number=internal_number,
        brand="SwedeSweets",
        name=name,
        weight_per_unit=1000,
        active=active,
    )


@pytest.mark.django_db
def test_business_catalog_lists_active_products_with_stock(
    monkeypatch,
):
    first = _product(
        internal_number=1,
        name="First",
    )
    second = _product(
        internal_number=2,
        name="Second",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            first.id: 8,
            second.id: 3,
        },
    )

    entries = list_business_catalog_entries()

    assert tuple(
        entry.product
        for entry in entries
    ) == (
        first,
        second,
    )

    assert tuple(
        entry.available_units
        for entry in entries
    ) == (
        8,
        3,
    )


@pytest.mark.django_db
def test_business_catalog_excludes_product_without_stock(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Unavailable",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 0,
        },
    )

    assert list_business_catalog_entries() == ()


@pytest.mark.django_db
def test_business_catalog_excludes_inactive_product(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Inactive",
        active=False,
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    assert list_business_catalog_entries() == ()


@pytest.mark.django_db
def test_business_catalog_prefetches_translations(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Translated later",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 4,
        },
    )

    (entry,) = list_business_catalog_entries()

    assert hasattr(
        entry.product,
        "prefetched_translations",
    )
