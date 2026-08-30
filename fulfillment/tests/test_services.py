from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from fulfillment.services import pack_order
from fulfillment.tests.conftest import TODAY
from inventory.services import create_batch
from orders.errors import InvalidOrderOperation
from orders.models import (
    Allocation,
    Order,
    OrderLine,
)


def _create_order_line(
    *,
    order: Order,
    product,
    quantity: int,
) -> OrderLine:
    return OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
    )


@pytest.mark.django_db
def test_pack_order_consumes_reservations_and_reduces_physical_stock(
    customer,
    apple,
):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )

    line = _create_order_line(
        order=order,
        product=apple,
        quantity=4,
    )

    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=4,
    )

    packed = pack_order(
        order=order,
    )

    packed.refresh_from_db()
    allocation.refresh_from_db()
    batch.refresh_from_db()

    assert packed.status == Order.Status.PACKED
    assert packed.packed_at is not None

    assert (
        allocation.status
        == Allocation.Status.CONSUMED
    )
    assert batch.quantity == 6


@pytest.mark.django_db
def test_pack_order_requires_reservations(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="has no reserved allocations",
    ):
        pack_order(
            order=order,
        )

    order.refresh_from_db()

    assert order.status == Order.Status.PLACED
    assert order.packed_at is None
