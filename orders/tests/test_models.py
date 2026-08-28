from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction

from inventory.services import create_batch
from orders.datatypes import BuyerInput
from orders.errors import (
    InvalidAllocationStatusTransition,
    InvalidOrderStatusTransition,
)
from orders.models import Allocation, Order, OrderLine
from orders.tests.conftest import TODAY

FUTURE_BEST_BEFORE = TODAY + timedelta(days=60)


@pytest.mark.django_db
def test_new_order_starts_as_business_draft(customer):
    order = Order.objects.create(customer=customer)

    assert order.channel == Order.Channel.BUSINESS
    assert order.status == Order.Status.DRAFT
    assert order.can_be_edited is False
    assert order.can_be_cancelled is True


@pytest.mark.django_db
def test_business_order_requires_customer():
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(
            channel=Order.Channel.BUSINESS,
            customer=None,
        )


@pytest.mark.django_db
def test_retail_order_can_have_anonymous_buyer():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    assert order.channel == Order.Channel.RETAIL
    assert order.customer is None


@pytest.mark.django_db
def test_retail_order_can_reference_persisted_customer(customer):
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=customer,
    )

    assert order.channel == Order.Channel.RETAIL
    assert order.customer == customer


@pytest.mark.django_db
def test_anonymous_retail_order_display_properties_use_empty_fallbacks():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    assert order.customer_name == ""
    assert order.customer_email == ""
    assert order.customer_phone_number == ""
    assert order.customer_country == ""
    assert order.customer_city == ""
    assert order.customer_address_line == ""
    assert order.customer_address == ""


@pytest.mark.django_db
def test_anonymous_retail_order_display_properties_use_buyer_snapshot():
    buyer = BuyerInput(
        name="Marie Dupont",
        email="marie@example.fr",
        phone_number="+33612345678",
        country="FR",
        city="Annecy",
        address_line="10 Rue du Lac",
        postal_code="74000",
    )

    order = Order(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    order.snapshot_buyer(buyer=buyer)
    order.save()

    assert order.customer_name == buyer.name
    assert order.customer_email == buyer.email
    assert order.customer_phone_number == buyer.phone_number
    assert order.customer_country == buyer.country
    assert order.customer_city == buyer.city
    assert order.customer_address_line == buyer.address_line
    assert buyer.address_line in order.customer_address
    assert buyer.city in order.customer_address


@pytest.mark.django_db
def test_customer_can_have_only_one_active_business_draft_order(customer):
    Order.objects.create(
        customer=customer,
        channel=Order.Channel.BUSINESS,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(
            customer=customer,
            channel=Order.Channel.BUSINESS,
        )


@pytest.mark.django_db
def test_retail_draft_does_not_conflict_with_business_draft(customer):
    business_draft = Order.objects.create(
        customer=customer,
        channel=Order.Channel.BUSINESS,
    )
    retail_draft = Order.objects.create(
        customer=customer,
        channel=Order.Channel.RETAIL,
    )

    assert business_draft.status == Order.Status.DRAFT
    assert retail_draft.status == Order.Status.DRAFT


@pytest.mark.django_db
def test_customer_can_create_new_draft_after_previous_draft_is_cancelled(customer):
    draft = Order.objects.create(customer=customer)
    draft.cancel(reason=Order.CancelReason.CUSTOMER_REQUEST)

    new_draft = Order.objects.create(customer=customer)

    assert new_draft.status == Order.Status.DRAFT


@pytest.mark.django_db
def test_order_snapshots_buyer_without_reading_customer_details(customer):
    buyer = BuyerInput(
        name="Marie Dupont",
        email="marie@example.fr",
        phone_number="+33612345678",
        country="FR",
        city="Annecy",
        address_line="10 Rue du Lac",
        postal_code="74000",
    )

    order = Order(customer=customer)
    order.snapshot_buyer(buyer=buyer)

    assert order.customer_name_snapshot == buyer.name
    assert order.customer_email_snapshot == buyer.email
    assert order.customer_phone_snapshot == buyer.phone_number
    assert order.customer_country_snapshot == buyer.country
    assert order.customer_city_snapshot == buyer.city
    assert order.customer_address_line_snapshot == buyer.address_line


@pytest.mark.django_db
def test_order_lifecycle_draft_to_placed_to_packed_to_delivered(customer):
    order = Order.objects.create(customer=customer)

    order.mark_as_placed()
    order.refresh_from_db()

    assert order.status == Order.Status.PLACED
    assert order.placed_at is not None
    assert order.can_be_edited is True
    assert order.can_be_cancelled is True

    order.mark_as_packed()
    order.refresh_from_db()

    assert order.status == Order.Status.PACKED
    assert order.packed_at is not None
    assert order.can_be_edited is False
    assert order.can_be_cancelled is False

    order.mark_as_delivered()
    order.refresh_from_db()

    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None
    assert order.can_be_cancelled is False


@pytest.mark.django_db
def test_order_rejects_invalid_status_transition(customer):
    order = Order.objects.create(customer=customer)

    with pytest.raises(InvalidOrderStatusTransition, match="Cannot transition"):
        order.mark_as_delivered()


@pytest.mark.django_db
def test_cancel_draft_order_sets_cancel_fields(customer):
    order = Order.objects.create(customer=customer)

    order.cancel(
        reason=Order.CancelReason.CUSTOMER_REQUEST,
        note="  Customer changed their mind.  ",
    )
    order.refresh_from_db()

    assert order.status == Order.Status.CANCELLED
    assert order.cancelled_at is not None
    assert order.cancel_reason == Order.CancelReason.CUSTOMER_REQUEST
    assert order.cancel_note == "Customer changed their mind."
    assert order.can_be_cancelled is False


@pytest.mark.django_db
def test_cancelled_order_cannot_be_placed(customer):
    order = Order.objects.create(customer=customer)
    order.cancel(reason=Order.CancelReason.OTHER)

    with pytest.raises(InvalidOrderStatusTransition, match="Cannot transition"):
        order.mark_as_placed()


@pytest.mark.django_db
def test_mark_as_edited_sets_edit_metadata(customer):
    order = Order.objects.create(customer=customer)

    order.mark_as_edited()
    order.refresh_from_db()

    assert order.edited_at is not None


@pytest.mark.django_db
def test_order_string_uses_primary_key(customer):
    order = Order.objects.create(customer=customer)

    assert str(order) == f"Order {order.pk}"


@pytest.mark.django_db
def test_order_line_string_uses_product_sku_quantity_and_unit(customer, apple):
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )

    assert str(line) == "SS-001: 10 stock_unit"


@pytest.mark.django_db
def test_allocation_can_be_consumed(customer, apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )
    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=10,
    )

    allocation.consume()
    allocation.refresh_from_db()

    assert allocation.status == Allocation.Status.CONSUMED


@pytest.mark.django_db
def test_allocation_can_be_cancelled(customer, apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )
    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=10,
    )

    allocation.cancel()
    allocation.refresh_from_db()

    assert allocation.status == Allocation.Status.CANCELLED


@pytest.mark.django_db
def test_consumed_allocation_cannot_be_cancelled(customer, apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )
    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=10,
    )

    allocation.consume()

    with pytest.raises(InvalidAllocationStatusTransition, match="Cannot transition"):
        allocation.cancel()


@pytest.mark.django_db
def test_allocation_string_contains_order_batch_and_quantity(customer, apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )
    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=10,
    )

    assert str(allocation) == f"{order.id} -> {batch.id}: 10"
