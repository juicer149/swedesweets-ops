from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from inventory.services import create_batch
from reservations.errors import InvalidAllocationStatusTransition
from orders.models import (
    Order,
    OrderLine,
)
from reservations.models import Allocation

TODAY = timezone.localdate()
FUTURE_BEST_BEFORE = TODAY + timedelta(days=60)


@pytest.mark.django_db
def test_allocation_may_have_temporary_expiry(product):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=5,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=5,
    )

    reserved_until = timezone.now() + timedelta(minutes=35)

    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=5,
        reserved_until=reserved_until,
    )

    allocation.refresh_from_db()

    assert allocation.status == Allocation.Status.RESERVED
    assert allocation.reserved_until == reserved_until


@pytest.mark.django_db
def test_allocation_can_be_consumed(customer, product):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=product,
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
def test_allocation_can_be_cancelled(customer, product):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=product,
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
def test_consumed_allocation_cannot_be_cancelled(customer, product):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=product,
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
def test_allocation_string_contains_order_batch_and_quantity(customer, product):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=FUTURE_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    order = Order.objects.create(customer=customer)
    line = OrderLine.objects.create(
        order=order,
        product=product,
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
