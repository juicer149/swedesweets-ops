from __future__ import annotations

import pytest

from products.errors import InvalidProductData
from products.models import Product, ProductProfile
from products.services import create_product, update_product, update_product_active
from products.tests.factories import product_factory


@pytest.mark.django_db
def test_create_product_creates_product_and_profile():
    result = create_product(
        internal_number=23,
        manufacturer="  Fazer   Finland ",
        brand="  Fazer ",
        name="  Tyrkisk   Peber ",
        weight_per_box=3000,
        vegan=True,
    )

    product = result.item

    assert result.created is True
    assert result.message == "Product added to the catalog."

    assert product.internal_number == 23
    assert product.manufacturer == "Fazer Finland"
    assert product.brand == "Fazer"
    assert product.name == "Tyrkisk Peber"
    assert product.weight_per_box == 3000
    assert product.vegan is True
    assert product.sku == "SS-023"

    assert ProductProfile.objects.filter(product=product).exists()


@pytest.mark.django_db
def test_create_product_returns_existing_product_with_same_sku():
    first = create_product(
        brand="OLW",
        name="Grill Chips",
        weight_per_box=275,
    )

    second = create_product(
        brand="  olw ",
        name="  Grill   Chips ",
        weight_per_box=275,
    )

    assert second.created is False
    assert second.item == first.item
    assert second.message == "Product already exists in the catalog."
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_create_product_returns_existing_product_with_same_internal_number():
    existing = create_product(
        internal_number=11,
        brand="OLW",
        name="Grill Chips",
        weight_per_box=275,
    )

    duplicate_number = create_product(
        internal_number=11,
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_box=3000,
    )

    assert duplicate_number.created is False
    assert duplicate_number.item == existing.item
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_create_product_rejects_invalid_data():
    with pytest.raises(InvalidProductData, match="brand must not be empty"):
        create_product(
            brand="",
            name="Apple",
            weight_per_box=5000,
        )

    with pytest.raises(InvalidProductData, match="weight_per_box must be at least"):
        create_product(
            brand="Generic",
            name="Apple",
            weight_per_box=0,
        )


@pytest.mark.django_db
def test_update_product_updates_editable_product_and_profile_fields():
    product = product_factory(
        internal_number=1,
        brand="Old Brand",
        name="Old Name",
        weight_per_box=1000,
    )

    updated = update_product(
        product=product,
        internal_number=2,
        manufacturer="  Fazer ",
        brand="  New Brand ",
        name="  New   Name ",
        active=False,
        vegan=True,
        description="  Nice candy.  ",
        ingredients="  Sugar, salt.  ",
        image_url="  https://example.com/product.jpg  ",
    )

    updated.refresh_from_db()
    updated.profile.refresh_from_db()

    assert updated.internal_number == 2
    assert updated.manufacturer == "Fazer"
    assert updated.brand == "New Brand"
    assert updated.name == "New Name"
    assert updated.active is False
    assert updated.vegan is True

    assert updated.profile.description == "Nice candy."
    assert updated.profile.ingredients == "Sugar, salt."
    assert updated.profile.image_url == "https://example.com/product.jpg"


@pytest.mark.django_db
def test_update_product_does_not_change_sku():
    product = product_factory(
        internal_number=1,
        brand="Old Brand",
        name="Old Name",
        weight_per_box=1000,
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
    product_factory(internal_number=1)
    product = product_factory(
        internal_number=2,
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_box=3000,
    )

    with pytest.raises(InvalidProductData, match="Product number 1 already exists"):
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

    updated = update_product_active(product=product, active=False)

    updated.refresh_from_db()

    assert updated.active is False
