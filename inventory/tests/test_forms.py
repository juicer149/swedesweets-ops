from __future__ import annotations

from datetime import date

import pytest

from inventory.forms import (
    BatchEditForm,
    BatchForm,
    ProductChoiceField,
    build_batch_edit_initial_data,
)
from inventory.services import create_batch
from inventory.tests.conftest import TODAY


@pytest.mark.django_db
def test_product_choice_field_label_from_instance(apple):
    field = ProductChoiceField(queryset=type(apple).objects.all())

    assert field.label_from_instance(apple) == "GENERIC-APPLE-5000 · Generic — Apple · 5000 g" 


@pytest.mark.django_db
def test_batch_form_accepts_valid_data(apple):
    form = BatchForm(
        data={
            "batch_id": "A-001",
            "product": str(apple.pk),
            "boxes": "10",
            "best_before": "2026-06-01",
            "location": "Shelf A1",
        }
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data["batch_id"] == "A-001"
    assert form.cleaned_data["product"] == apple
    assert form.cleaned_data["boxes"] == 10
    assert form.cleaned_data["best_before"] == date(2026, 6, 1)
    assert form.cleaned_data["location"] == "Shelf A1"


@pytest.mark.django_db
def test_batch_form_allows_empty_batch_id_for_auto_generation(apple):
    form = BatchForm(
        data={
            "batch_id": "",
            "product": str(apple.pk),
            "boxes": "10",
            "best_before": "2026-06-01",
            "location": "Shelf A1",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["batch_id"] == ""


@pytest.mark.django_db
def test_batch_form_rejects_inactive_product(inactive_product):
    form = BatchForm(
        data={
            "batch_id": "A-001",
            "product": str(inactive_product.pk),
            "boxes": "10",
            "best_before": "2026-06-01",
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "product" in form.errors


@pytest.mark.django_db
def test_batch_form_rejects_zero_boxes(apple):
    form = BatchForm(
        data={
            "batch_id": "A-001",
            "product": str(apple.pk),
            "boxes": "0",
            "best_before": "2026-06-01",
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "boxes" in form.errors


@pytest.mark.django_db
def test_batch_form_rejects_invalid_best_before_date(apple):
    form = BatchForm(
        data={
            "batch_id": "A-001",
            "product": str(apple.pk),
            "boxes": "10",
            "best_before": "not-a-date",
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "best_before" in form.errors


def test_batch_form_configures_product_select_metadata():
    form = BatchForm()

    assert form.fields["product"].widget.attrs["data-enhanced-select"] == "true"
    assert form.fields["product"].widget.attrs["data-enhanced-select-search"] == "true"


@pytest.mark.django_db
def test_batch_edit_form_accepts_valid_data():
    form = BatchEditForm(
        data={
            "boxes": "0",
            "best_before": "2026-06-01",
            "location": "Shelf A1",
        }
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data["boxes"] == 0
    assert form.cleaned_data["best_before"] == date(2026, 6, 1)
    assert form.cleaned_data["location"] == "Shelf A1"


def test_batch_edit_form_rejects_negative_boxes():
    form = BatchEditForm(
        data={
            "boxes": "-1",
            "best_before": "2026-06-01",
            "location": "Shelf A1",
        }
    )

    assert not form.is_valid()
    assert "boxes" in form.errors


@pytest.mark.django_db
def test_build_batch_edit_initial_data(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    assert build_batch_edit_initial_data(batch) == {
        "boxes": 10,
        "best_before": date(2026, 6, 1),
        "location": "Shelf A1",
    }
