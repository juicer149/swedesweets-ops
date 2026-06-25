from __future__ import annotations

import pytest

from products.forms import (
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_INACTIVE,
    ProductEditForm,
    ProductForm,
    build_product_edit_initial_data,
)
from products.models import Product, ProductProfile
from products.tests.factories import product_factory


def valid_product_form_data(**overrides):
    data = {
        "internal_number": "",
        "manufacturer": "Fazer",
        "brand": "Fazer",
        "name": "Tyrkisk Peber",
        "customer_facing_name_fr": "",
        "stock_unit": Product.StockUnit.BOX,
        "weight_per_unit": "3000",
        "vegan": "on",
    }
    data.update(overrides)
    return data


def valid_product_edit_form_data(**overrides):
    data = {
        "internal_number": "23",
        "manufacturer": "Fazer",
        "brand": "Fazer",
        "name": "Tyrkisk Peber",
        "customer_facing_name_fr": "",
        "active": PRODUCT_STATUS_ACTIVE,
        "vegan": "on",
        "description": "Classic candy.",
        "ingredients": "Sugar.",
        "image_url": "https://example.com/product.jpg",
    }
    data.update(overrides)
    return data


def test_product_form_accepts_valid_data():
    form = ProductForm(data=valid_product_form_data())

    assert form.is_valid(), form.errors

    assert form.cleaned_data["internal_number"] is None
    assert form.cleaned_data["manufacturer"] == "Fazer"
    assert form.cleaned_data["brand"] == "Fazer"
    assert form.cleaned_data["name"] == "Tyrkisk Peber"
    assert form.cleaned_data["customer_facing_name_fr"] == ""
    assert form.cleaned_data["stock_unit"] == Product.StockUnit.BOX
    assert form.cleaned_data["weight_per_unit"] == 3000
    assert form.cleaned_data["vegan"] is True


def test_product_form_accepts_customer_facing_french_name():
    form = ProductForm(
        data=valid_product_form_data(
            customer_facing_name_fr="Bonbon français",
        )
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["customer_facing_name_fr"] == "Bonbon français"


def test_product_form_accepts_piece_stock_unit():
    form = ProductForm(
        data=valid_product_form_data(stock_unit=Product.StockUnit.PIECE)
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["stock_unit"] == Product.StockUnit.PIECE


def test_product_form_rejects_missing_required_fields():
    form = ProductForm(data=valid_product_form_data(brand="", name=""))

    assert not form.is_valid()

    assert "brand" in form.errors
    assert "name" in form.errors


def test_product_form_rejects_invalid_weight_per_unit():
    form = ProductForm(data=valid_product_form_data(weight_per_unit="0"))

    assert not form.is_valid()

    assert "weight_per_unit" in form.errors


def test_product_form_rejects_invalid_stock_unit():
    form = ProductForm(data=valid_product_form_data(stock_unit="pallet"))

    assert not form.is_valid()

    assert "stock_unit" in form.errors


def test_product_form_configures_vegan_toggle_metadata():
    form = ProductForm()

    field = form.fields["vegan"]

    assert field.tag_toggle is True
    assert field.tag_toggle_label == "Vegan"
    assert field.tag_toggle_icon == "leaf"


def test_product_edit_form_accepts_valid_data():
    form = ProductEditForm(data=valid_product_edit_form_data())

    assert form.is_valid(), form.errors

    assert form.cleaned_data["internal_number"] == 23
    assert form.cleaned_data["customer_facing_name_fr"] == ""
    assert form.active_value is True


def test_product_edit_form_accepts_customer_facing_french_name():
    form = ProductEditForm(
        data=valid_product_edit_form_data(
            customer_facing_name_fr="Bonbon français",
        )
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["customer_facing_name_fr"] == "Bonbon français"


def test_product_edit_form_maps_inactive_choice_to_false():
    form = ProductEditForm(
        data=valid_product_edit_form_data(active=PRODUCT_STATUS_INACTIVE)
    )

    assert form.is_valid(), form.errors
    assert form.active_value is False


def test_product_edit_form_rejects_invalid_status_choice():
    form = ProductEditForm(data=valid_product_edit_form_data(active="archived"))

    assert not form.is_valid()

    assert "active" in form.errors


@pytest.mark.django_db
def test_build_product_edit_initial_data_without_profile():
    product = product_factory(
        internal_number=23,
        manufacturer="Fazer",
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
        stock_unit=Product.StockUnit.BOX,
        vegan=True,
    )

    ProductProfile.objects.filter(product=product).delete()

    initial = build_product_edit_initial_data(product)

    assert initial == {
        "internal_number": 23,
        "manufacturer": "Fazer",
        "brand": "Fazer",
        "name": "Tyrkisk Peber",
        "customer_facing_name_fr": "",
        "active": PRODUCT_STATUS_ACTIVE,
        "vegan": True,
        "description": "",
        "ingredients": "",
        "image_url": "",
    }


@pytest.mark.django_db
def test_build_product_edit_initial_data_with_profile():
    product = product_factory(
        internal_number=23,
        manufacturer="Fazer",
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
        stock_unit=Product.StockUnit.BOX,
        vegan=True,
    )

    profile = product.profile
    profile.description = "Classic candy."
    profile.ingredients = "Sugar."
    profile.image_url = "https://example.com/product.jpg"
    profile.save()

    initial = build_product_edit_initial_data(product)

    assert initial["description"] == "Classic candy."
    assert initial["ingredients"] == "Sugar."
    assert initial["image_url"] == "https://example.com/product.jpg"
    assert initial["customer_facing_name_fr"] == ""


@pytest.mark.django_db
def test_build_product_edit_initial_data_includes_customer_facing_french_name():
    product = product_factory(
        internal_number=23,
        manufacturer="Fazer",
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
        stock_unit=Product.StockUnit.BOX,
    )

    product.translations.create(
        language_code="fr",
        name="Bonbon français",
    )

    initial = build_product_edit_initial_data(product)

    assert initial["customer_facing_name_fr"] == "Bonbon français"
