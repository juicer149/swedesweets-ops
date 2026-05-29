from __future__ import annotations

from decimal import Decimal

import pytest

from products.selectors import (
    PRODUCT_FILTER_ACTIVE,
    PRODUCT_FILTER_INACTIVE,
    get_product_by_sku,
    get_product_delivered_demand_summary,
    list_products,
)
from products.tests.factories import product_factory


@pytest.mark.django_db
def test_get_product_by_sku_strips_and_uppercases_input():
    product = product_factory(
        internal_number=23,
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
    )

    assert get_product_by_sku(sku=" ss-023 ") == product


@pytest.mark.django_db
def test_list_products_can_filter_active_products():
    active_product = product_factory(
        internal_number=1,
        brand="Active",
        name="Product",
    )
    inactive_product = product_factory(
        internal_number=2,
        brand="Inactive",
        name="Product",
    )
    inactive_product.active = False
    inactive_product.save(update_fields=["active"])

    products = list(list_products(status=PRODUCT_FILTER_ACTIVE))

    assert active_product in products
    assert inactive_product not in products


@pytest.mark.django_db
def test_list_products_can_filter_inactive_products():
    active_product = product_factory(
        internal_number=1,
        brand="Active",
        name="Product",
    )
    inactive_product = product_factory(
        internal_number=2,
        brand="Inactive",
        name="Product",
    )
    inactive_product.active = False
    inactive_product.save(update_fields=["active"])

    products = list(list_products(status=PRODUCT_FILTER_INACTIVE))

    assert inactive_product in products
    assert active_product not in products


@pytest.mark.django_db
def test_list_products_defaults_to_number_sort():
    second = product_factory(
        internal_number=2,
        brand="B",
        name="Second",
    )
    first = product_factory(
        internal_number=1,
        brand="A",
        name="First",
    )

    assert list(list_products()) == [first, second]


@pytest.mark.django_db
def test_list_products_accepts_known_sort_key():
    b_product = product_factory(
        internal_number=2,
        brand="B",
        name="Banana",
    )
    a_product = product_factory(
        internal_number=1,
        brand="A",
        name="Apple",
    )

    assert list(list_products(sort="brand")) == [a_product, b_product]


@pytest.mark.django_db
def test_list_products_can_sort_by_weight_per_unit():
    light = product_factory(
        internal_number=1,
        brand="Light",
        name="Product",
        weight_per_unit=100,
    )
    heavy = product_factory(
        internal_number=2,
        brand="Heavy",
        name="Product",
        weight_per_unit=500,
    )

    assert list(list_products(sort="weight")) == [light, heavy]


@pytest.mark.django_db
def test_list_products_can_sort_by_stock_unit():
    box_product = product_factory(
        internal_number=1,
        brand="Box",
        name="Product",
    )
    piece_product = product_factory(
        internal_number=2,
        brand="Piece",
        name="Product",
        stock_unit="piece",
    )

    assert list(list_products(sort="unit")) == [box_product, piece_product]


@pytest.mark.django_db
def test_get_product_delivered_demand_summary_is_empty_without_delivered_orders():
    product = product_factory()

    summary = get_product_delivered_demand_summary(product=product)

    assert summary.delivered_order_count == 0
    assert summary.delivered_quantity == 0
    assert summary.average_quantity_per_delivered_order == Decimal("0.0")
    assert summary.last_delivered_at is None
