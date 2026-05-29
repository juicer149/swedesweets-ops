from __future__ import annotations

from decimal import Decimal

import pytest

from products.errors import InvalidProductData
from products.models import Product
from products.tests.factories import product_factory


@pytest.mark.django_db
def test_product_save_normalizes_fields_and_generates_sku():
    product = Product.objects.create(
        brand="  olw ",
        name="  Grill   Chips ",
        manufacturer="  Orkla   Snacks ",
        weight_per_unit=275,
    )

    assert product.brand == "olw"
    assert product.name == "Grill Chips"
    assert product.manufacturer == "Orkla Snacks"
    assert product.sku == "OLW-GRILL_CHIPS-275"
    assert product.stock_unit == Product.StockUnit.BOX


@pytest.mark.django_db
def test_product_save_generates_internal_number_sku():
    product = Product.objects.create(
        internal_number=7,
        brand="OLW",
        name="Grill Chips",
        weight_per_unit=275,
    )

    assert product.sku == "SS-007"


@pytest.mark.django_db
def test_product_weight_per_unit_cannot_change_after_creation():
    product = product_factory(weight_per_unit=275)

    product.weight_per_unit = 500

    with pytest.raises(
        InvalidProductData,
        match="weight_per_unit cannot be changed after product creation",
    ):
        product.save(update_fields=["weight_per_unit"])


@pytest.mark.django_db
def test_product_stock_unit_cannot_change_after_creation():
    product = product_factory(stock_unit=Product.StockUnit.BOX)

    product.stock_unit = Product.StockUnit.PIECE

    with pytest.raises(
        InvalidProductData,
        match="stock_unit cannot be changed after product creation",
    ):
        product.save(update_fields=["stock_unit"])


@pytest.mark.django_db
def test_product_sku_cannot_change_after_creation():
    product = product_factory()

    product.sku = "CUSTOM-SKU"

    with pytest.raises(
        InvalidProductData,
        match="sku cannot be changed after product creation",
    ):
        product.save(update_fields=["sku"])


@pytest.mark.django_db
def test_product_catalog_fields_can_change_without_changing_sku():
    product = product_factory(
        internal_number=12,
        brand="Old Brand",
        name="Old Name",
        weight_per_unit=1000,
    )

    original_sku = product.sku

    product.brand = "New Brand"
    product.name = "New Name"
    product.save(update_fields=["brand", "name"])

    product.refresh_from_db()

    assert product.brand == "New Brand"
    assert product.name == "New Name"
    assert product.sku == original_sku


@pytest.mark.django_db
def test_display_name_returns_brand_and_product_name():
    product = product_factory(brand="Tyrkisk Peber", name="Original")

    assert product.display_name == "Tyrkisk Peber — Original"


@pytest.mark.django_db
def test_catalog_label_includes_code_display_name_and_weight():
    product = product_factory(
        internal_number=23,
        brand="Tyrkisk Peber",
        name="Original",
        weight_per_unit=2200,
    )

    assert product.catalog_label == "#23 · Tyrkisk Peber — Original · 2200 g / box"


@pytest.mark.django_db
def test_product_formats_stock_quantity_label_for_boxes():
    product = product_factory(stock_unit=Product.StockUnit.BOX)

    assert product.stock_quantity_label(1) == "1 box"
    assert product.stock_quantity_label(2) == "2 boxes"


@pytest.mark.django_db
def test_product_formats_stock_quantity_label_for_pieces():
    product = product_factory(stock_unit=Product.StockUnit.PIECE)

    assert product.stock_quantity_label(1) == "1 piece"
    assert product.stock_quantity_label(2) == "2 pieces"


@pytest.mark.django_db
def test_product_converts_grams_to_units_rounding_up():
    product = product_factory(weight_per_unit=5000)

    assert product.grams_to_units(grams=1) == 1
    assert product.grams_to_units(grams=5000) == 1
    assert product.grams_to_units(grams=5001) == 2


@pytest.mark.django_db
def test_product_rejects_non_positive_grams():
    product = product_factory(weight_per_unit=5000)

    with pytest.raises(InvalidProductData, match="grams must be positive"):
        product.grams_to_units(grams=0)


@pytest.mark.django_db
def test_product_converts_kg_to_units_rounding_up_to_whole_units():
    product = product_factory(weight_per_unit=5000)

    assert product.kg_to_units(kg=Decimal("5.0")) == 1
    assert product.kg_to_units(kg=Decimal("5.001")) == 2


@pytest.mark.django_db
def test_product_rejects_non_positive_kg():
    product = product_factory(weight_per_unit=5000)

    with pytest.raises(InvalidProductData, match="kg must be positive"):
        product.kg_to_units(kg=Decimal("0"))


@pytest.mark.django_db
def test_product_converts_units_to_grams_and_kg():
    product = product_factory(weight_per_unit=5000)

    assert product.units_to_grams(units=3) == 15000
    assert product.units_to_kg(units=3) == Decimal("15")


@pytest.mark.django_db
def test_product_rejects_non_positive_units():
    product = product_factory(weight_per_unit=5000)

    with pytest.raises(InvalidProductData, match="units must be positive"):
        product.units_to_grams(units=0)


@pytest.mark.django_db
def test_product_profile_string_uses_product_sku():
    product = product_factory(internal_number=9)

    assert str(product.profile) == "SS-009"
