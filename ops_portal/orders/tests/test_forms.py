from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from business.tests.factories import standard_business_offer_factory
from customers.tests.factories import customer_factory
from inventory.tests.factories import batch_factory
from ops_portal.orders.forms import (
    MAX_UNITS_PER_PRODUCT_PER_ORDER,
    OrderCancelForm,
    OrderCreateForm,
    OrderLineForm,
    OrderLineFormSet,
    BusinessOfferChoiceField,
    build_order_line_initial_data,
    build_order_line_inputs,
)
from orders.models import Order
from orders.tests.factories import order_line_factory
from pricing.models import CommercialPrice, PriceAmount
from products.tests.factories import product_factory
from products.units import OrderUnit


TODAY = timezone.localdate()

STOCK_EARLY_BEST_BEFORE = (
    TODAY + timedelta(days=60)
)
STOCK_LATE_BEST_BEFORE = (
    TODAY + timedelta(days=90)
)


def _stock_apple(
    apple,
) -> None:
    batch_factory(
        product=apple,
        quantity=100,
        batch_id="A-001",
        best_before=STOCK_EARLY_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    batch_factory(
        product=apple,
        quantity=50,
        batch_id="A-002",
        best_before=STOCK_LATE_BEST_BEFORE,
        location="Shelf A2",
        today=TODAY,
    )


def _standard_business_offer(
    product,
) -> CommercialPrice:
    return standard_business_offer_factory(
        product=product,
    )


def _business_batch_offer(
    *,
    product,
    batch,
) -> CommercialPrice:
    offer = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    PriceAmount.objects.create(
        commercial_price=offer,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("8.50"),
    )

    return offer


@pytest.mark.django_db
def test_order_create_form_accepts_customer():
    customer = customer_factory()

    form = OrderCreateForm(
        data={
            "customer": str(
                customer.pk
            ),
        }
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["customer"]
        == customer
    )


@pytest.mark.django_db
def test_order_create_form_rejects_missing_customer():
    form = OrderCreateForm(
        data={},
    )

    assert not form.is_valid()
    assert "customer" in form.errors


@pytest.mark.django_db
def test_business_offer_choice_field_label_includes_product_offer_and_stock():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )
    offer = _standard_business_offer(
        apple,
    )

    field = BusinessOfferChoiceField(
        queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: 12,
        },
    )

    assert (
        field.label_from_instance(
            offer
        )
        == "#1 · Generic — Apple · 5000 g / Box · 12 left"
    )


@pytest.mark.django_db
def test_order_line_form_accepts_valid_line():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": OrderUnit.STOCK,
            "quantity": "10",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: 100,
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["commercial_offer"]
        == offer
    )
    assert (
        form.cleaned_data["quantity"]
        == Decimal("10")
    )
    assert (
        form.cleaned_data["unit"]
        == OrderUnit.STOCK
    )
    assert (
        form.cleaned_data[
            "quantity_in_units"
        ]
        == 10
    )
    assert form.has_line_data is True


@pytest.mark.django_db
def test_order_line_form_allows_empty_line():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": "",
            "unit": "",
            "quantity": "",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
    )

    assert form.is_valid(), form.errors
    assert form.has_line_data is False


@pytest.mark.django_db
def test_order_line_form_requires_offer_when_quantity_is_present():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": "",
            "unit": OrderUnit.STOCK,
            "quantity": "10",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
    )

    assert not form.is_valid()
    assert "commercial_offer" in form.errors


@pytest.mark.django_db
def test_order_line_form_requires_quantity_when_product_is_present():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": OrderUnit.STOCK,
            "quantity": "",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
    )

    assert not form.is_valid()
    assert "quantity" in form.errors


@pytest.mark.django_db
def test_order_line_form_defaults_missing_unit_to_stock_unit():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": "",
            "quantity": "5",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: 100,
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["unit"]
        == OrderUnit.STOCK
    )


@pytest.mark.django_db
def test_order_line_form_accepts_kg_quantity():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": OrderUnit.KG,
            "quantity": "12.5",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: 100,
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["quantity"]
        == Decimal("12.5")
    )
    assert (
        form.cleaned_data["unit"]
        == OrderUnit.KG
    )
    assert (
        form.cleaned_data[
            "quantity_in_units"
        ]
        == 3
    )


@pytest.mark.django_db
def test_order_line_form_accepts_grams_quantity():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": OrderUnit.GRAMS,
            "quantity": "12000",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: 100,
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["quantity"]
        == Decimal("12000")
    )
    assert (
        form.cleaned_data["unit"]
        == OrderUnit.GRAMS
    )
    assert (
        form.cleaned_data[
            "quantity_in_units"
        ]
        == 3
    )


@pytest.mark.django_db
def test_order_line_form_accepts_line_before_formset_stock_validation():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": OrderUnit.STOCK,
            "quantity": "11",
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: 10,
        },
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data[
            "quantity_in_units"
        ]
        == 11
    )


@pytest.mark.django_db
def test_order_line_form_rejects_unusually_large_line():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    form = OrderLineForm(
        data={
            "commercial_offer": str(
                offer.pk
            ),
            "unit": OrderUnit.STOCK,
            "quantity": str(
                MAX_UNITS_PER_PRODUCT_PER_ORDER
                + 1
            ),
        },
        offer_queryset=CommercialPrice.objects.filter(
            pk=offer.pk,
        ),
        available_units_by_offer_id={
            offer.id: (
                MAX_UNITS_PER_PRODUCT_PER_ORDER
                + 10
            ),
        },
    )

    assert not form.is_valid()
    assert "quantity" in form.errors


@pytest.mark.django_db
def test_order_line_formset_requires_at_least_one_line():
    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-commercial_offer": "",
            "form-0-unit": "",
            "form-0-quantity": "",
        },
    )

    assert not formset.is_valid()

    assert (
        "Add at least one order line."
        in formset.non_form_errors()
    )


@pytest.mark.django_db
def test_order_line_formset_rejects_more_than_available_stock():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    _stock_apple(
        apple,
    )
    offer = _standard_business_offer(
        apple,
    )

    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-commercial_offer": str(
                offer.pk
            ),
            "form-0-unit": (
                OrderUnit.STOCK
            ),
            "form-0-quantity": "151",
        },
    )

    assert not formset.is_valid()

    assert (
        "Only 150 boxes available for Generic — Apple."
        in formset.non_form_errors()
    )


@pytest.mark.django_db
def test_order_line_formset_accepts_available_stock():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    _stock_apple(
        apple,
    )
    offer = _standard_business_offer(
        apple,
    )

    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-commercial_offer": str(
                offer.pk
            ),
            "form-0-unit": (
                OrderUnit.STOCK
            ),
            "form-0-quantity": "150",
        },
    )

    assert (
        formset.is_valid()
    ), formset.errors

    inputs = build_order_line_inputs(
        formset
    )

    assert len(inputs) == 1
    assert (
        inputs[0].commercial_offer_id
        == offer.pk
    )
    assert (
        inputs[0].quantity
        == Decimal("150")
    )
    assert (
        inputs[0].unit
        == OrderUnit.STOCK
    )


@pytest.mark.django_db
def test_order_line_formset_validates_availability_per_offer():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    batch_factory(
        product=apple,
        quantity=5,
        batch_id="A-ORDINARY",
        best_before=STOCK_LATE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    special_batch = batch_factory(
        product=apple,
        quantity=5,
        batch_id="A-SPECIAL",
        best_before=STOCK_EARLY_BEST_BEFORE,
        location="Shelf A2",
        today=TODAY,
    )

    standard_offer = _standard_business_offer(
        apple,
    )
    special_offer = _business_batch_offer(
        product=apple,
        batch=special_batch,
    )

    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-commercial_offer": str(
                standard_offer.pk
            ),
            "form-0-unit": OrderUnit.STOCK,
            "form-0-quantity": "6",
            "form-1-commercial_offer": str(
                special_offer.pk
            ),
            "form-1-unit": OrderUnit.STOCK,
            "form-1-quantity": "1",
        },
    )

    assert not formset.is_valid()

    assert (
        "Only 5 boxes available for Generic — Apple."
        in formset.non_form_errors()
    )


@pytest.mark.django_db
def test_order_line_formset_applies_order_limit_across_offers_for_same_product():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    batch_factory(
        product=apple,
        quantity=MAX_UNITS_PER_PRODUCT_PER_ORDER,
        batch_id="A-ORDINARY",
        best_before=STOCK_LATE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    special_batch = batch_factory(
        product=apple,
        quantity=10,
        batch_id="A-SPECIAL",
        best_before=STOCK_EARLY_BEST_BEFORE,
        location="Shelf A2",
        today=TODAY,
    )

    standard_offer = _standard_business_offer(
        apple,
    )
    special_offer = _business_batch_offer(
        product=apple,
        batch=special_batch,
    )

    formset = OrderLineFormSet(
        data={
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-commercial_offer": str(
                standard_offer.pk
            ),
            "form-0-unit": OrderUnit.STOCK,
            "form-0-quantity": str(
                MAX_UNITS_PER_PRODUCT_PER_ORDER
            ),
            "form-1-commercial_offer": str(
                special_offer.pk
            ),
            "form-1-unit": OrderUnit.STOCK,
            "form-1-quantity": "1",
        },
    )

    assert not formset.is_valid()

    assert (
        "Generic — Apple is unusually large."
        in formset.non_form_errors()[0]
    )


@pytest.mark.django_db
def test_build_order_line_initial_data():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    offer = _standard_business_offer(
        apple,
    )

    order = Order.objects.create(
        customer=customer,
    )
    order.mark_as_placed()

    order_line_factory(
        order=order,
        product=apple,
        commercial_offer=offer,
        quantity=10,
    )

    assert (
        build_order_line_initial_data(
            order
        )
        == [
            {
                "commercial_offer": offer.id,
                "unit": OrderUnit.STOCK,
                "quantity": 10,
                "offer_label": (
                    "#1 · Generic — Apple · 5000 g / Box"
                ),
            }
        ]
    )


def test_order_cancel_form_accepts_reason_and_note():
    form = OrderCancelForm(
        data={
            "reason": (
                Order.CancelReason.CUSTOMER_REQUEST
            ),
            "note": (
                "Customer changed their mind."
            ),
        }
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["reason"]
        == Order.CancelReason.CUSTOMER_REQUEST
    )
    assert (
        form.cleaned_data["note"]
        == "Customer changed their mind."
    )


def test_order_cancel_form_rejects_invalid_reason():
    form = OrderCancelForm(
        data={
            "reason": "bad_reason",
            "note": "",
        }
    )

    assert not form.is_valid()
    assert "reason" in form.errors
