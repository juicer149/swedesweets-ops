from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from inventory.services import create_batch
from orders.datatypes import OrderLineInput
from orders.forms import (
    MAX_UNITS_PER_PRODUCT_PER_ORDER,
    OrderCancelForm,
    OrderCreateForm,
    OrderLineForm,
    OrderLineFormSet,
    ProductChoiceField,
    build_order_line_initial_data,
    build_order_line_inputs,
)
from orders.models import Order, OrderLine
from orders.product_choices import build_product_choice_context
from orders.services import create_order
from orders.tests.conftest import TODAY
from products.units import ORDER_UNIT_KG, ORDER_UNIT_STOCK, ORDER_UNIT_GRAMS


@pytest.mark.django_db
def test_order_create_form_accepts_customer(customer):
    form = OrderCreateForm(
        data={
            "customer": str(customer.pk),
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["customer"] == customer


@pytest.mark.django_db
def test_order_create_form_rejects_missing_customer():
    form = OrderCreateForm(data={})

    assert not form.is_valid()
    assert "customer" in form.errors


@pytest.mark.django_db
def test_product_choice_field_label_includes_internal_number_weight_and_stock(apple):
    field = ProductChoiceField(
        queryset=type(apple).objects.all(),
        available_units_by_product_id={
            apple.id: 12,
        },
    )

    assert field.label_from_instance(apple) == (
        "#1 · Generic — Apple · 5000 g / Box · 12 boxes"
    )


@pytest.mark.django_db
def test_order_line_form_accepts_valid_line(apple):
    form = OrderLineForm(
        data={
            "product": str(apple.pk),
            "unit": ORDER_UNIT_STOCK,
            "quantity": "10",
        },
        product_queryset=type(apple).objects.filter(pk=apple.pk),
        available_units_by_product_id={
            apple.id: 100,
        },
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data["product"] == apple
    assert form.cleaned_data["quantity"] == Decimal("10")
    assert form.cleaned_data["unit"] == ORDER_UNIT_STOCK
    assert form.cleaned_data["quantity_in_units"] == 10
    assert form.has_line_data is True


@pytest.mark.django_db
def test_order_line_form_allows_empty_line(apple):
    form = OrderLineForm(
        data={
            "product": "",
            "unit": "",
            "quantity": "",
        },
        product_queryset=type(apple).objects.filter(pk=apple.pk),
    )

    assert form.is_valid(), form.errors
    assert form.has_line_data is False


@pytest.mark.django_db
def test_order_line_form_requires_product_when_quantity_is_present(apple):
    form = OrderLineForm(
        data={
            "product": "",
            "unit": ORDER_UNIT_STOCK,
            "quantity": "10",
        },
        product_queryset=type(apple).objects.filter(pk=apple.pk),
    )

    assert not form.is_valid()
    assert "product" in form.errors


@pytest.mark.django_db
def test_order_line_form_requires_quantity_when_product_is_present(apple):
    form = OrderLineForm(
        data={
            "product": str(apple.pk),
            "unit": ORDER_UNIT_STOCK,
            "quantity": "",
        },
        product_queryset=type(apple).objects.filter(pk=apple.pk),
    )

    assert not form.is_valid()
    assert "quantity" in form.errors


@pytest.mark.django_db
def test_order_line_form_defaults_missing_unit_to_kg(apple):
    form = OrderLineForm(
        data={
            "product": str(apple.pk),
            "unit": "",
            "quantity": "5",
        },
        product_queryset=type(apple).objects.filter(pk=apple.pk),
        available_units_by_product_id={
            apple.id: 100,
        },
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["unit"] == ORDER_UNIT_STOCK


@pytest.mark.django_db
def test_order_line_form_rejects_unusually_large_line(apple):
    form = OrderLineForm(
        data={
            "product": str(apple.pk),
            "unit": ORDER_UNIT_STOCK,
            "quantity": str(MAX_UNITS_PER_PRODUCT_PER_ORDER + 1),
        },
        product_queryset=type(apple).objects.filter(pk=apple.pk),
        available_units_by_product_id={
            apple.id: 1000,
        },
    )

    assert not form.is_valid()
    assert "quantity" in form.errors


@pytest.mark.django_db
def test_order_line_formset_requires_at_least_one_line(apple):
    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-product": "",
            "form-0-unit": "",
            "form-0-quantity": "",
        },
    )

    assert not formset.is_valid()
    assert "Add at least one order line." in formset.non_form_errors()


@pytest.mark.django_db
def test_order_line_formset_rejects_more_than_available_stock(apple, stocked_inventory):
    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-product": str(apple.pk),
            "form-0-unit": ORDER_UNIT_STOCK,
            "form-0-quantity": "151",
        },
    )

    assert not formset.is_valid()
    assert (
        "Only 150 boxes available for Generic — Apple."
        in formset.non_form_errors()
    )


@pytest.mark.django_db
def test_order_line_formset_accepts_available_stock(apple, stocked_inventory):
    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-product": str(apple.pk),
            "form-0-unit": ORDER_UNIT_STOCK,
            "form-0-quantity": "150",
        },
    )

    assert formset.is_valid(), formset.errors

    inputs = build_order_line_inputs(formset)

    assert len(inputs) == 1
    assert inputs[0].product == apple
    assert inputs[0].quantity == Decimal("150")
    assert inputs[0].unit == ORDER_UNIT_STOCK


@pytest.mark.django_db
def test_build_product_choice_context_includes_only_orderable_products(
    apple,
    banana,
    stocked_inventory,
    inactive_product,
):
    context = build_product_choice_context()

    products = list(context.queryset)

    assert apple in products
    assert banana in products
    assert inactive_product not in products

    assert context.available_units_by_product_id[apple.id] == 150
    assert context.available_units_by_product_id[banana.id] == 80


@pytest.mark.django_db
def test_build_product_choice_context_excludes_product_with_only_expired_stock(
    apple,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )

    context = build_product_choice_context()

    assert list(context.queryset) == []
    assert apple.id not in context.available_units_by_product_id


@pytest.mark.django_db
def test_build_product_choice_context_includes_existing_order_product_even_if_inactive(
    customer,
    inactive_product,
):
    order = Order.objects.create(customer=customer)
    order.lines.create(
        product=inactive_product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
    )

    context = build_product_choice_context(order=order)

    assert list(context.queryset) == [inactive_product]
    assert context.available_units_by_product_id[inactive_product.id] == 1


@pytest.mark.django_db
def test_build_order_line_initial_data(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    assert build_order_line_initial_data(order) == [
        {
            "product": apple.id,
            "unit": ORDER_UNIT_STOCK,
            "quantity": Decimal("10.000"),
        }
    ]


def test_order_cancel_form_accepts_reason_and_note():
    form = OrderCancelForm(
        data={
            "reason": Order.CancelReason.CUSTOMER_REQUEST,
            "note": "Customer changed their mind.",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["reason"] == Order.CancelReason.CUSTOMER_REQUEST
    assert form.cleaned_data["note"] == "Customer changed their mind."


def test_order_cancel_form_rejects_invalid_reason():
    form = OrderCancelForm(
        data={
            "reason": "bad_reason",
            "note": "",
        }
    )

    assert not form.is_valid()
    assert "reason" in form.errors
