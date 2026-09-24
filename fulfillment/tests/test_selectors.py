from __future__ import annotations

import pytest

from fulfillment.selectors import (
    get_packaging_list,
    get_packed_lines,
)
from fulfillment.services import pack_order
from orders.models import (
    Order,
    OrderLine,
)
from orders.tests.factories import order_line_factory
from reservations.models import Allocation


def _create_line(
    *,
    order: Order,
    product,
    quantity: int,
) -> OrderLine:
    return order_line_factory(
        order=order,
        product=product,
        quantity=quantity,
    )


def _create_placed_order(
    *,
    customer,
) -> Order:
    order = Order.objects.create(
        customer=customer,
    )
    order.mark_as_placed()

    return order


@pytest.mark.django_db
def test_packaging_list_comes_from_reserved_allocations(
    apple,
    banana,
    customer,
    stocked_inventory,
):
    order = _create_placed_order(
        customer=customer,
    )

    apple_line = _create_line(
        order=order,
        product=apple,
        quantity=120,
    )
    banana_line = _create_line(
        order=order,
        product=banana,
        quantity=5,
    )

    Allocation.objects.create(
        order=order,
        order_line=apple_line,
        batch=stocked_inventory["apple_early"],
        quantity=100,
    )
    Allocation.objects.create(
        order=order,
        order_line=apple_line,
        batch=stocked_inventory["apple_late"],
        quantity=20,
    )
    Allocation.objects.create(
        order=order,
        order_line=banana_line,
        batch=stocked_inventory["banana"],
        quantity=5,
    )

    pick_lines = get_packaging_list(
        order=order,
    )

    assert [
        (
            line.sku,
            line.batch_id,
            line.location,
            line.quantity,
        )
        for line in pick_lines
    ] == [
        (
            "SS-001",
            "A-001",
            "Shelf A1",
            100,
        ),
        (
            "SS-001",
            "A-002",
            "Shelf A2",
            20,
        ),
        (
            "SS-002",
            "B-001",
            "Shelf B1",
            5,
        ),
    ]


@pytest.mark.django_db
def test_packed_lines_come_from_consumed_allocations(
    apple,
    customer,
    stocked_inventory,
):
    order = _create_placed_order(
        customer=customer,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=10,
    )

    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=stocked_inventory["apple_early"],
        quantity=10,
    )

    packed = pack_order(
        order=order,
    )

    pick_lines = get_packed_lines(
        order=packed,
    )

    assert [
        (
            line.sku,
            line.batch_id,
            line.location,
            line.quantity,
        )
        for line in pick_lines
    ] == [
        (
            "SS-001",
            "A-001",
            "Shelf A1",
            10,
        )
    ]
