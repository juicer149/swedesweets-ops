from __future__ import annotations

from decimal import Decimal

import pytest

from products.errors import InvalidProductData, UnsupportedOrderUnit
from products.tests.factories import product_factory
from products.units import normalize_order_unit, quantity_to_boxes


@pytest.mark.parametrize(
    ("raw_unit", "expected"),
    [
        ("boxes", "boxes"),
        (" BOXES ", "boxes"),
        ("kg", "kg"),
        (" KG ", "kg"),
        ("grams", "grams"),
        (" GRAMS ", "grams"),
    ],
)
def test_normalize_order_unit_accepts_supported_units(raw_unit, expected):
    assert normalize_order_unit(raw_unit) == expected


def test_normalize_order_unit_rejects_unsupported_unit():
    with pytest.raises(UnsupportedOrderUnit, match="Unsupported order unit"):
        normalize_order_unit("pallets")


@pytest.mark.django_db
def test_quantity_to_boxes_accepts_whole_boxes():
    product = product_factory(weight_per_box=5000)

    assert quantity_to_boxes(
        product=product,
        quantity=Decimal("3"),
        unit="boxes",
    ) == 3


@pytest.mark.django_db
def test_quantity_to_boxes_rejects_fractional_boxes():
    product = product_factory(weight_per_box=5000)

    with pytest.raises(InvalidProductData, match="box orders must use a whole number"):
        quantity_to_boxes(
            product=product,
            quantity=Decimal("1.5"),
            unit="boxes",
        )


@pytest.mark.django_db
def test_quantity_to_boxes_converts_grams_rounding_up():
    product = product_factory(weight_per_box=5000)

    assert quantity_to_boxes(
        product=product,
        quantity=Decimal("5001"),
        unit="grams",
    ) == 2


@pytest.mark.django_db
def test_quantity_to_boxes_rejects_fractional_grams():
    product = product_factory(weight_per_box=5000)

    with pytest.raises(InvalidProductData, match="gram orders must use a whole number"):
        quantity_to_boxes(
            product=product,
            quantity=Decimal("1.5"),
            unit="grams",
        )


@pytest.mark.django_db
def test_quantity_to_boxes_converts_kg_rounding_up():
    product = product_factory(weight_per_box=5000)

    assert quantity_to_boxes(
        product=product,
        quantity=Decimal("5.001"),
        unit="kg",
    ) == 2


@pytest.mark.django_db
def test_quantity_to_boxes_rejects_non_positive_quantity():
    product = product_factory(weight_per_box=5000)

    with pytest.raises(InvalidProductData, match="quantity must be positive"):
        quantity_to_boxes(
            product=product,
            quantity=Decimal("0"),
            unit="kg",
        )
