from __future__ import annotations

from decimal import Decimal

import pytest

from products.errors import InvalidProductData, UnsupportedOrderUnit
from products.models import Product
from products.tests.factories import product_factory
from products.units import normalize_order_unit, quantity_to_units


@pytest.mark.parametrize(
    ("raw_unit", "expected"),
    [
        ("stock_unit", "stock_unit"),
        (" STOCK_UNIT ", "stock_unit"),
        ("kg", "kg"),
        (" KG ", "kg"),
        ("grams", "grams"),
        (" GRAMS ", "grams"),
    ],
)
def test_normalize_order_unit_accepts_supported_units(raw_unit, expected):
    assert normalize_order_unit(raw_unit) == expected


@pytest.mark.parametrize(
    "raw_unit",
    [
        "boxes",
        " BOXES ",
        "box",
        "piece",
        "pieces",
        "pallets",
        "",
    ],
)
def test_normalize_order_unit_rejects_unsupported_unit(raw_unit):
    with pytest.raises(UnsupportedOrderUnit, match="Unsupported order unit"):
        normalize_order_unit(raw_unit)


@pytest.mark.django_db
def test_quantity_to_units_accepts_whole_stock_units():
    product = product_factory(weight_per_unit=5000)

    assert quantity_to_units(
        product=product,
        quantity=Decimal("3"),
        unit="stock_unit",
    ) == 3


@pytest.mark.django_db
def test_quantity_to_units_rejects_fractional_stock_units():
    product = product_factory(weight_per_unit=5000)

    with pytest.raises(
        InvalidProductData,
        match="stock unit orders must use a whole number",
    ):
        quantity_to_units(
            product=product,
            quantity=Decimal("1.5"),
            unit="stock_unit",
        )


@pytest.mark.django_db
def test_quantity_to_units_converts_grams_rounding_up():
    product = product_factory(weight_per_unit=5000)

    assert quantity_to_units(
        product=product,
        quantity=Decimal("5001"),
        unit="grams",
    ) == 2


@pytest.mark.django_db
def test_quantity_to_units_rejects_fractional_grams():
    product = product_factory(weight_per_unit=5000)

    with pytest.raises(InvalidProductData, match="gram orders must use a whole number"):
        quantity_to_units(
            product=product,
            quantity=Decimal("1.5"),
            unit="grams",
        )


@pytest.mark.django_db
def test_quantity_to_units_converts_kg_rounding_up():
    product = product_factory(weight_per_unit=5000)

    assert quantity_to_units(
        product=product,
        quantity=Decimal("5.001"),
        unit="kg",
    ) == 2


@pytest.mark.django_db
def test_quantity_to_units_rejects_non_positive_quantity():
    product = product_factory(weight_per_unit=5000)

    with pytest.raises(InvalidProductData, match="quantity must be positive"):
        quantity_to_units(
            product=product,
            quantity=Decimal("0"),
            unit="kg",
        )


@pytest.mark.django_db
def test_quantity_to_units_uses_product_stock_unit_independently_of_label():
    product = product_factory(
        weight_per_unit=60,
        stock_unit=Product.StockUnit.PIECE,
    )

    assert quantity_to_units(
        product=product,
        quantity=Decimal("3"),
        unit="stock_unit",
    ) == 3
