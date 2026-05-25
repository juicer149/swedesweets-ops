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
        weight_per_box=275,
    )

    assert product.brand == "olw"
    assert product.name == "Grill Chips"
    assert product.manufacturer == "Orkla Snacks"
    assert product.sku == "OLW-GRILL_CHIPS-275"


@pytest.mark.django_db
def test_product_save_generates_internal_number_sku():
    product = Product.objects.create(
        internal_number=7,
        brand="OLW",
        name="Grill Chips",
        weight_per_box=275,
    )

    assert product.sku == "SS-007"


@pytest.mark.django_db
def test_product_weight_per_box_cannot_change_after_creation():
    product = product_factory(weight_per_box=275)

    product.weight_per_box = 500

    with pytest.raises(
        InvalidProductData,
        match="weight_per_box cannot be changed after product creation",
    ):
        product.save(update_fields=["weight_per_box"])


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
        weight_per_box=1000,
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
def test_display_name_returns_product_name():
    product = product_factory(name="Tyrkisk Peber")

    assert product.display_name() == "Tyrkisk Peber"


@pytest.mark.django_db
def test_product_converts_grams_to_boxes_rounding_up():
    product = product_factory(weight_per_box=5000)

    assert product.grams_to_boxes(grams=1) == 1
    assert product.grams_to_boxes(grams=5000) == 1
    assert product.grams_to_boxes(grams=5001) == 2


@pytest.mark.django_db
def test_product_rejects_non_positive_grams():
    product = product_factory(weight_per_box=5000)

    with pytest.raises(InvalidProductData, match="grams must be positive"):
        product.grams_to_boxes(grams=0)


@pytest.mark.django_db
def test_product_converts_kg_to_boxes_rounding_up_to_whole_boxes():
    product = product_factory(weight_per_box=5000)

    assert product.kg_to_boxes(kg=Decimal("5.0")) == 1
    assert product.kg_to_boxes(kg=Decimal("5.001")) == 2


@pytest.mark.django_db
def test_product_rejects_non_positive_kg():
    product = product_factory(weight_per_box=5000)

    with pytest.raises(InvalidProductData, match="kg must be positive"):
        product.kg_to_boxes(kg=Decimal("0"))


@pytest.mark.django_db
def test_product_converts_boxes_to_grams_and_kg():
    product = product_factory(weight_per_box=5000)

    assert product.boxes_to_grams(boxes=3) == 15000
    assert product.boxes_to_kg(boxes=3) == Decimal("15")


@pytest.mark.django_db
def test_product_rejects_non_positive_boxes():
    product = product_factory(weight_per_box=5000)

    with pytest.raises(InvalidProductData, match="boxes must be positive"):
        product.boxes_to_grams(boxes=0)


@pytest.mark.django_db
def test_product_profile_string_uses_product_sku():
    product = product_factory(internal_number=9)

    assert str(product.profile) == "SS-009"
