from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from inventory.tests.factories import batch_factory
from ops_portal.inventory.forms import (
    BatchEditForm,
    BatchForm,
    ProductChoiceField,
    build_batch_edit_initial_data,
)
from products.tests.factories import product_factory

TODAY = timezone.localdate()
FUTURE_BEST_BEFORE = TODAY + timedelta(days=60)
FUTURE_BEST_BEFORE_INPUT = f"{FUTURE_BEST_BEFORE:%Y-%m-%d}"


def _make_product(
    *,
    name: str = "Apple",
    weight_per_unit: int = 5000,
    active: bool = True,
):
    product = product_factory(
        brand="Generic",
        name=name,
        weight_per_unit=weight_per_unit,
    )

    if product.active != active:
        product.active = active
        product.save(update_fields=["active"])

    return product


@pytest.mark.django_db
def test_product_choice_field_label_from_instance():
    product = _make_product()

    field = ProductChoiceField(
        queryset=type(product).objects.all(),
    )

    assert field.label_from_instance(product) == (
        "GENERIC-APPLE-5000 · Generic — Apple · 5000 g / Box"
    )


@pytest.mark.django_db
def test_batch_form_accepts_valid_data():
    product = _make_product()

    form = BatchForm(
        data={
            "product": str(product.pk),
            "quantity": "10",
            "best_before": FUTURE_BEST_BEFORE_INPUT,
            "location": "Shelf A1",
        }
    )

    assert form.is_valid(), form.errors

    assert "batch_id" not in form.fields
    assert "batch_id" not in form.cleaned_data
    assert form.cleaned_data["product"] == product
    assert form.cleaned_data["quantity"] == 10
    assert form.cleaned_data["best_before"] == FUTURE_BEST_BEFORE
    assert form.cleaned_data["location"] == "Shelf A1"


@pytest.mark.django_db
def test_batch_form_rejects_inactive_product():
    product = _make_product(
        name="Inactive Product",
        weight_per_unit=7000,
        active=False,
    )

    form = BatchForm(
        data={
            "product": str(product.pk),
            "quantity": "10",
            "best_before": FUTURE_BEST_BEFORE_INPUT,
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "product" in form.errors


@pytest.mark.django_db
def test_batch_form_rejects_zero_quantity():
    product = _make_product()

    form = BatchForm(
        data={
            "product": str(product.pk),
            "quantity": "0",
            "best_before": FUTURE_BEST_BEFORE_INPUT,
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "quantity" in form.errors


@pytest.mark.django_db
def test_batch_form_rejects_invalid_best_before_date():
    product = _make_product()

    form = BatchForm(
        data={
            "product": str(product.pk),
            "quantity": "10",
            "best_before": "not-a-date",
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "best_before" in form.errors


def test_batch_form_configures_product_select_metadata():
    form = BatchForm()

    assert form.fields["product"].widget.attrs["data-enhanced-select"] == "true"
    assert (
        form.fields["product"].widget.attrs["data-enhanced-select-search"]
        == "true"
    )


@pytest.mark.django_db
def test_batch_edit_form_accepts_valid_data():
    form = BatchEditForm(
        data={
            "quantity": "0",
            "best_before": FUTURE_BEST_BEFORE_INPUT,
            "location": "Shelf A1",
        }
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data["quantity"] == 0
    assert form.cleaned_data["best_before"] == FUTURE_BEST_BEFORE
    assert form.cleaned_data["location"] == "Shelf A1"


def test_batch_edit_form_rejects_negative_quantity():
    form = BatchEditForm(
        data={
            "quantity": "-1",
            "best_before": FUTURE_BEST_BEFORE_INPUT,
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "quantity" in form.errors


@pytest.mark.django_db
def test_build_batch_edit_initial_data():
    product = _make_product()

    batch = batch_factory(
        product=product,
        batch_id="A-001",
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    assert build_batch_edit_initial_data(batch) == {
        "quantity": 10,
        "best_before": FUTURE_BEST_BEFORE,
        "location": "Shelf A1",
    }
