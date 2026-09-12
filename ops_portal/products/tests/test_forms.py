from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from PIL import Image

from ops_portal.products.forms import (
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_INACTIVE,
    ProductEditForm,
    ProductForm,
    build_product_edit_initial_data,
)
from products.models import (
    Product,
    ProductProfile,
)
from products.tests.factories import (
    product_factory,
)


def valid_product_form_data(
    **overrides,
):
    data = {
        "internal_number": "",
        "manufacturer": "Fazer",
        "brand": "Fazer",
        "name": "Tyrkisk Peber",
        "customer_facing_name_fr": "",
        "stock_unit": (
            Product.StockUnit.BOX
        ),
        "weight_per_unit": "3000",
        "category": (
            ProductProfile.Category.CANDY
        ),
        "vegan": "on",
        "description": "Classic candy.",
        "ingredients": "Sugar.",
    }

    data.update(
        overrides
    )

    return data


def valid_product_edit_form_data(
    **overrides,
):
    data = {
        "internal_number": "23",
        "manufacturer": "Fazer",
        "brand": "Fazer",
        "name": "Tyrkisk Peber",
        "customer_facing_name_fr": "",
        "active": PRODUCT_STATUS_ACTIVE,
        "category": (
            ProductProfile.Category.CANDY
        ),
        "vegan": "on",
        "description": "Classic candy.",
        "ingredients": "Sugar.",
    }

    data.update(
        overrides
    )

    return data


def uploaded_image(
    *,
    name: str = "product.png",
    image_format: str = "PNG",
) -> SimpleUploadedFile:
    output = BytesIO()

    Image.new(
        "RGB",
        (
            40,
            40,
        ),
    ).save(
        output,
        format=image_format,
    )

    content_type = (
        "image/jpeg"
        if image_format == "JPEG"
        else "image/png"
    )

    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type=content_type,
    )


def test_product_form_accepts_valid_data():
    form = ProductForm(
        data=valid_product_form_data(),
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["internal_number"]
        is None
    )
    assert (
        form.cleaned_data["manufacturer"]
        == "Fazer"
    )
    assert (
        form.cleaned_data["brand"]
        == "Fazer"
    )
    assert (
        form.cleaned_data["name"]
        == "Tyrkisk Peber"
    )
    assert (
        form.cleaned_data[
            "customer_facing_name_fr"
        ]
        == ""
    )
    assert (
        form.cleaned_data["stock_unit"]
        == Product.StockUnit.BOX
    )
    assert (
        form.cleaned_data["weight_per_unit"]
        == 3000
    )
    assert (
        form.cleaned_data["category"]
        == ProductProfile.Category.CANDY
    )
    assert (
        form.cleaned_data["vegan"]
        is True
    )
    assert (
        form.cleaned_data["description"]
        == "Classic candy."
    )
    assert (
        form.cleaned_data["ingredients"]
        == "Sugar."
    )
    assert (
        form.cleaned_data["image"]
        is None
    )


def test_product_form_accepts_png_image():
    form = ProductForm(
        data=valid_product_form_data(),
        files={
            "image": uploaded_image(),
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["image"].name
        == "product.png"
    )


def test_product_form_accepts_jpeg_image():
    form = ProductForm(
        data=valid_product_form_data(),
        files={
            "image": uploaded_image(
                name="product.jpg",
                image_format="JPEG",
            ),
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["image"].name
        == "product.jpg"
    )


def test_product_form_rejects_non_image_upload():
    upload = SimpleUploadedFile(
        "product.txt",
        b"not an image",
        content_type="text/plain",
    )

    form = ProductForm(
        data=valid_product_form_data(),
        files={
            "image": upload,
        },
    )

    assert not form.is_valid()
    assert "image" in form.errors


def test_product_form_accepts_customer_facing_french_name():
    form = ProductForm(
        data=valid_product_form_data(
            customer_facing_name_fr=(
                "Bonbon français"
            ),
        )
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data[
            "customer_facing_name_fr"
        ]
        == "Bonbon français"
    )


def test_product_form_accepts_piece_stock_unit():
    form = ProductForm(
        data=valid_product_form_data(
            stock_unit=(
                Product.StockUnit.PIECE
            ),
        )
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["stock_unit"]
        == Product.StockUnit.PIECE
    )


def test_product_form_accepts_empty_category():
    form = ProductForm(
        data=valid_product_form_data(
            category="",
        )
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["category"]
        == ""
    )


def test_product_form_rejects_invalid_category():
    form = ProductForm(
        data=valid_product_form_data(
            category="drinks",
        )
    )

    assert not form.is_valid()
    assert "category" in form.errors


def test_product_form_rejects_missing_required_fields():
    form = ProductForm(
        data=valid_product_form_data(
            brand="",
            name="",
        )
    )

    assert not form.is_valid()
    assert "brand" in form.errors
    assert "name" in form.errors


def test_product_form_rejects_invalid_weight_per_unit():
    form = ProductForm(
        data=valid_product_form_data(
            weight_per_unit="0",
        )
    )

    assert not form.is_valid()
    assert (
        "weight_per_unit"
        in form.errors
    )


def test_product_form_rejects_invalid_stock_unit():
    form = ProductForm(
        data=valid_product_form_data(
            stock_unit="pallet",
        )
    )

    assert not form.is_valid()
    assert "stock_unit" in form.errors


def test_product_form_configures_vegan_toggle_metadata():
    form = ProductForm()

    field = form.fields["vegan"]

    assert field.tag_toggle is True
    assert (
        field.tag_toggle_label
        == "Vegan"
    )
    assert (
        field.tag_toggle_icon
        == "leaf"
    )


def test_product_edit_form_accepts_valid_data():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data()
        ),
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["internal_number"]
        == 23
    )
    assert (
        form.cleaned_data[
            "customer_facing_name_fr"
        ]
        == ""
    )
    assert (
        form.cleaned_data["category"]
        == ProductProfile.Category.CANDY
    )
    assert form.active_value is True
    assert (
        form.cleaned_data["image"]
        is None
    )
    assert (
        form.cleaned_data["remove_image"]
        is False
    )


def test_product_edit_form_accepts_new_image():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data()
        ),
        files={
            "image": uploaded_image(),
        },
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["image"].name
        == "product.png"
    )


def test_product_edit_form_accepts_remove_image():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data(
                remove_image="on",
            )
        ),
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["remove_image"]
        is True
    )


def test_product_edit_form_rejects_upload_and_remove_together():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data(
                remove_image="on",
            )
        ),
        files={
            "image": uploaded_image(),
        },
    )

    assert not form.is_valid()
    assert (
        "remove_image"
        in form.errors
    )


def test_product_edit_form_accepts_customer_facing_french_name():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data(
                customer_facing_name_fr=(
                    "Bonbon français"
                ),
            )
        )
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data[
            "customer_facing_name_fr"
        ]
        == "Bonbon français"
    )


def test_product_edit_form_maps_inactive_choice_to_false():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data(
                active=(
                    PRODUCT_STATUS_INACTIVE
                ),
            )
        )
    )

    assert form.is_valid(), form.errors
    assert form.active_value is False


def test_product_edit_form_rejects_invalid_status_choice():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data(
                active="archived",
            )
        )
    )

    assert not form.is_valid()
    assert "active" in form.errors


def test_product_edit_form_rejects_invalid_category():
    form = ProductEditForm(
        data=(
            valid_product_edit_form_data(
                category="drinks",
            )
        )
    )

    assert not form.is_valid()
    assert "category" in form.errors


@pytest.mark.django_db
def test_build_product_edit_initial_data_without_profile():
    product = product_factory(
        internal_number=23,
        manufacturer="Fazer",
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
        stock_unit=(
            Product.StockUnit.BOX
        ),
        vegan=True,
    )

    ProductProfile.objects.filter(
        product=product,
    ).delete()

    initial = (
        build_product_edit_initial_data(
            product
        )
    )

    assert initial == {
        "internal_number": 23,
        "manufacturer": "Fazer",
        "brand": "Fazer",
        "name": "Tyrkisk Peber",
        "customer_facing_name_fr": "",
        "active": PRODUCT_STATUS_ACTIVE,
        "category": "",
        "vegan": True,
        "description": "",
        "ingredients": "",
    }


@pytest.mark.django_db
def test_build_product_edit_initial_data_with_profile():
    product = product_factory(
        internal_number=23,
        manufacturer="Fazer",
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
        stock_unit=(
            Product.StockUnit.BOX
        ),
        vegan=True,
    )

    profile = product.profile
    profile.category = (
        ProductProfile.Category.CANDY
    )
    profile.description = (
        "Classic candy."
    )
    profile.ingredients = "Sugar."

    profile.save(
        update_fields=[
            "category",
            "description",
            "ingredients",
        ]
    )

    initial = (
        build_product_edit_initial_data(
            product
        )
    )

    assert (
        initial["category"]
        == ProductProfile.Category.CANDY
    )
    assert (
        initial["description"]
        == "Classic candy."
    )
    assert (
        initial["ingredients"]
        == "Sugar."
    )
    assert (
        initial[
            "customer_facing_name_fr"
        ]
        == ""
    )


@pytest.mark.django_db
def test_build_product_edit_initial_data_does_not_include_image_fields():
    product = product_factory()

    initial = (
        build_product_edit_initial_data(
            product
        )
    )

    assert "image" not in initial
    assert "thumbnail" not in initial
    assert "remove_image" not in initial


@pytest.mark.django_db
def test_build_product_edit_initial_data_includes_customer_facing_french_name():
    product = product_factory(
        internal_number=23,
        manufacturer="Fazer",
        brand="Fazer",
        name="Tyrkisk Peber",
        weight_per_unit=3000,
        stock_unit=(
            Product.StockUnit.BOX
        ),
    )

    product.translations.create(
        language_code="fr",
        name="Bonbon français",
    )

    initial = (
        build_product_edit_initial_data(
            product
        )
    )

    assert (
        initial[
            "customer_facing_name_fr"
        ]
        == "Bonbon français"
    )
