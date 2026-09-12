from __future__ import annotations

import pytest

from products.errors import InvalidProductData
from products.models import Product, ProductProfile
from products.services import (
    create_product,
    update_product,
    update_product_active,
)
from products.tests.factories import product_factory


@pytest.mark.django_db
def test_create_product_creates_product_and_profile():
    result = create_product(
        internal_number=23,
        manufacturer="  Fazer   Finland ",
        brand="  Fazer ",
        name="  Tyrkisk   Peber ",
        weight_per_unit=3000,
        stock_unit=Product.StockUnit.BOX,
        vegan=True,
        category=ProductProfile.Category.CANDY,
        description="  Classic candy.  ",
        ingredients="  Sugar.  ",
    )

    product = result.item

    assert result.created is True
    assert (
        result.message
        == "Product added to the catalog."
    )

    assert product.internal_number == 23
    assert product.manufacturer == "Fazer Finland"
    assert product.brand == "Fazer"
    assert product.name == "Tyrkisk Peber"
    assert product.weight_per_unit == 3000
    assert (
        product.stock_unit
        == Product.StockUnit.BOX
    )
    assert product.vegan is True
    assert product.sku == "SS-023"

    profile = ProductProfile.objects.get(
        product=product,
    )

    assert (
        profile.category
        == ProductProfile.Category.CANDY
    )
    assert profile.description == "Classic candy."
    assert profile.ingredients == "Sugar."
    assert not profile.image
    assert not profile.thumbnail


@pytest.mark.django_db
def test_create_product_accepts_piece_stock_unit():
    result = create_product(
        internal_number=24,
        brand="Cloetta",
        name="Kexchoklad",
        weight_per_unit=60,
        stock_unit=Product.StockUnit.PIECE,
    )

    assert result.created is True
    assert (
        result.item.stock_unit
        == Product.StockUnit.PIECE
    )
    assert result.item.weight_per_unit == 60


@pytest.mark.django_db
def test_create_product_accepts_empty_profile_category():
    result = create_product(
        brand="OLW",
        name="Grill Chips",
        weight_per_unit=275,
        category="",
    )

    assert result.created is True
    assert result.item.profile.category == ""


@pytest.mark.django_db
def test_create_product_rejects_invalid_profile_category():
    with pytest.raises(
        InvalidProductData,
        match="Unsupported product category",
    ):
        create_product(
            brand="Generic",
            name="Drink",
            weight_per_unit=500,
            category="drinks",
        )


@pytest.mark.django_db
def test_create_product_returns_existing_product_with_same_sku():
    first = create_product(
        brand="OLW",
        name="Grill Chips",
        weight_per_unit=275,
    )

    second = create_product(
        brand="  olw ",
        name="  Grill   Chips ",
        weight_per_unit=275,
    )

    assert second.created is False
    assert second.item == first.item
    assert (
        second.message
        == "Product already exists in the catalog."
    )
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_create_product_returns_existing_product_with_same_internal_number():
    existing = create_product(
        internal_number=11,
        brand="OLW",
        name="Grill Chips",
        weight_per_unit=275,
    )

    duplicate_number = create_product(
        internal_number=11,
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
    )

    assert duplicate_number.created is False
    assert duplicate_number.item == existing.item
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_create_product_rejects_invalid_data():
    with pytest.raises(
        InvalidProductData,
        match="brand must not be empty",
    ):
        create_product(
            brand="",
            name="Apple",
            weight_per_unit=5000,
        )

    with pytest.raises(
        InvalidProductData,
        match="weight_per_unit must be at least",
    ):
        create_product(
            brand="Generic",
            name="Apple",
            weight_per_unit=0,
        )

    with pytest.raises(
        InvalidProductData,
        match="Unsupported stock unit",
    ):
        create_product(
            brand="Generic",
            name="Apple",
            weight_per_unit=5000,
            stock_unit="pallet",
        )


@pytest.mark.django_db
def test_update_product_updates_editable_product_and_profile_fields():
    product = product_factory(
        internal_number=1,
        brand="Old Brand",
        name="Old Name",
        weight_per_unit=1000,
    )

    updated = update_product(
        product=product,
        internal_number=2,
        manufacturer="  Fazer ",
        brand="  New Brand ",
        name="  New   Name ",
        active=False,
        vegan=True,
        category=ProductProfile.Category.CHIPS,
        description="  Nice chips.  ",
        ingredients="  Potatoes, salt.  ",
    )

    updated.refresh_from_db()
    updated.profile.refresh_from_db()

    assert updated.internal_number == 2
    assert updated.manufacturer == "Fazer"
    assert updated.brand == "New Brand"
    assert updated.name == "New Name"
    assert updated.active is False
    assert updated.vegan is True

    assert (
        updated.profile.category
        == ProductProfile.Category.CHIPS
    )
    assert (
        updated.profile.description
        == "Nice chips."
    )
    assert (
        updated.profile.ingredients
        == "Potatoes, salt."
    )


@pytest.mark.django_db
def test_update_product_can_clear_profile_fields():
    product = product_factory()

    profile = product.profile
    profile.category = (
        ProductProfile.Category.CANDY
    )
    profile.description = "Description"
    profile.ingredients = "Ingredients"
    profile.save(
        update_fields=[
            "category",
            "description",
            "ingredients",
        ]
    )

    updated = update_product(
        product=product,
        internal_number=product.internal_number,
        manufacturer=product.manufacturer,
        brand=product.brand,
        name=product.name,
        active=product.active,
        vegan=product.vegan,
        category="",
        description="",
        ingredients="",
    )

    updated.profile.refresh_from_db()

    assert updated.profile.category == ""
    assert updated.profile.description == ""
    assert updated.profile.ingredients == ""


@pytest.mark.django_db
def test_update_product_does_not_change_existing_image_fields():
    product = product_factory()

    profile = product.profile
    profile.image.name = (
        "products/originals/example.png"
    )
    profile.thumbnail.name = (
        "products/thumbnails/example.webp"
    )
    profile.save(
        update_fields=[
            "image",
            "thumbnail",
        ]
    )

    updated = update_product(
        product=product,
        internal_number=product.internal_number,
        manufacturer=product.manufacturer,
        brand=product.brand,
        name="Updated name",
        active=product.active,
        vegan=product.vegan,
        category=profile.category,
        description=profile.description,
        ingredients=profile.ingredients,
    )

    updated.profile.refresh_from_db()

    assert (
        updated.profile.image.name
        == "products/originals/example.png"
    )
    assert (
        updated.profile.thumbnail.name
        == "products/thumbnails/example.webp"
    )


@pytest.mark.django_db
def test_update_product_rejects_invalid_profile_category():
    product = product_factory()

    with pytest.raises(
        InvalidProductData,
        match="Unsupported product category",
    ):
        update_product(
            product=product,
            internal_number=product.internal_number,
            manufacturer=product.manufacturer,
            brand=product.brand,
            name=product.name,
            active=True,
            vegan=False,
            category="drinks",
        )


@pytest.mark.django_db
def test_update_product_does_not_change_sku():
    product = product_factory(
        internal_number=1,
        brand="Old Brand",
        name="Old Name",
        weight_per_unit=1000,
    )

    original_sku = product.sku

    updated = update_product(
        product=product,
        internal_number=2,
        manufacturer="",
        brand="New Brand",
        name="New Name",
        active=True,
        vegan=False,
    )

    assert updated.sku == original_sku


@pytest.mark.django_db
def test_update_product_rejects_duplicate_internal_number():
    product_factory(
        internal_number=1,
    )

    product = product_factory(
        internal_number=2,
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
    )

    with pytest.raises(
        InvalidProductData,
        match="Product number 1 already exists",
    ):
        update_product(
            product=product,
            internal_number=1,
            manufacturer="",
            brand="Fazer",
            name="Tyrkisk Peber",
            active=True,
            vegan=False,
        )


@pytest.mark.django_db
def test_update_product_active_updates_only_status():
    product = product_factory()

    assert product.active is True

    updated = update_product_active(
        product=product,
        active=False,
    )

    updated.refresh_from_db()

    assert updated.active is False
