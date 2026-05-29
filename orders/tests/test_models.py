from __future__ import annotations

import pytest

from inventory.services import create_batch
from orders.errors import (
    InvalidAllocationStatusTransition,
    InvalidOrderStatusTransition,
)
from orders.models import Allocation, Order, OrderLine
from orders.tests.conftest import TODAY


@pytest.mark.django_db
def test_new_order_starts_as_draft(customer):
    order = Order.objects.create(customer=customer)

    assert order.status == Order.Status.DRAFT
    assert order.can_be_edited is False
    assert order.can_be_cancelled is True


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
        best_before=TODAY.replace(month=6, day=1),
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
        best_before=TODAY.replace(month=6, day=1),
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
        best_before=TODAY.replace(month=6, day=1),
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
        best_before=TODAY.replace(month=6, day=1),
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
