from __future__ import annotations

import pytest

from fulfillment.services import pack_order
from orders.models import (
    Allocation,
    Order,
    OrderLine,
)
from orders.selectors import (
    count_packed_orders,
    count_placed_orders,
    get_customer_order_summary,
    get_packaging_list,
    get_packed_lines,
    list_customer_orders,
    list_orders,
    list_packed_orders_for_dashboard,
    list_placed_orders_for_dashboard,
)


def _create_line(
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


@pytest.mark.django_db
def test_list_orders_filters_by_status(
    customer,
    other_customer,
):
    placed = _create_placed_order(
        customer=customer,
    )
    draft = Order.objects.create(
        customer=other_customer,
        status=Order.Status.DRAFT,
    )

    orders = list(
        list_orders(
            status=Order.Status.PLACED,
        )
    )

    assert placed in orders
    assert draft not in orders


@pytest.mark.django_db
def test_list_orders_annotates_total_quantity(
    customer,
    apple,
):
    order = _create_placed_order(
        customer=customer,
    )
    _create_line(
        order=order,
        product=apple,
        quantity=10,
    )

    listed = list_orders().get(
        pk=order.pk,
    )

    assert listed.total_quantity == 10


@pytest.mark.django_db
def test_list_customer_orders_returns_only_customer_orders(
    customer,
    other_customer,
):
    first = Order.objects.create(
        customer=customer,
        status=Order.Status.PLACED,
    )
    second = Order.objects.create(
        customer=customer,
        status=Order.Status.PACKED,
    )
    other = Order.objects.create(
        customer=other_customer,
        status=Order.Status.PLACED,
    )

    orders = list_customer_orders(
        customer=customer,
    )

    assert first in orders
    assert second in orders
    assert other not in orders


@pytest.mark.django_db
def test_get_customer_order_summary_is_empty_without_orders(
    customer,
):
    summary = get_customer_order_summary(
        customer=customer,
    )

    assert summary.total_orders == 0
    assert summary.placed_orders == 0
    assert summary.packed_orders == 0
    assert summary.delivered_orders == 0
    assert summary.cancelled_orders == 0
    assert summary.last_ordered_at is None


@pytest.mark.django_db
def test_get_customer_order_summary_counts_orders_by_status(
    customer,
):
    placed = Order.objects.create(
        customer=customer,
    )
    placed.mark_as_placed()

    packed = Order.objects.create(
        customer=customer,
    )
    packed.mark_as_placed()
    packed.mark_as_packed()

    delivered = Order.objects.create(
        customer=customer,
    )
    delivered.mark_as_placed()
    delivered.mark_as_packed()
    delivered.mark_as_delivered()

    cancelled = Order.objects.create(
        customer=customer,
    )
    cancelled.cancel(
        reason=(
            Order.CancelReason.CUSTOMER_REQUEST
        ),
    )

    summary = get_customer_order_summary(
        customer=customer,
    )

    assert summary.total_orders == 4
    assert summary.placed_orders == 1
    assert summary.packed_orders == 1
    assert summary.delivered_orders == 1
    assert summary.cancelled_orders == 1
    assert summary.last_ordered_at is not None


@pytest.mark.django_db
def test_list_placed_orders_for_dashboard_returns_only_placed_orders(
    customer,
    other_customer,
):
    placed = _create_placed_order(
        customer=customer,
    )

    packed = Order.objects.create(
        customer=other_customer,
    )
    packed.mark_as_placed()
    packed.mark_as_packed()

    rows = list(
        list_placed_orders_for_dashboard(
            limit=3,
        )
    )

    assert placed in rows
    assert packed not in rows


@pytest.mark.django_db
def test_list_packed_orders_for_dashboard_returns_only_packed_orders(
    customer,
    other_customer,
):
    placed = _create_placed_order(
        customer=customer,
    )

    packed = Order.objects.create(
        customer=other_customer,
    )
    packed.mark_as_placed()
    packed.mark_as_packed()

    rows = list(
        list_packed_orders_for_dashboard(
            limit=3,
        )
    )

    assert packed in rows
    assert placed not in rows


@pytest.mark.django_db
def test_count_placed_and_packed_orders(
    customer,
    other_customer,
):
    _create_placed_order(
        customer=customer,
    )

    packed = Order.objects.create(
        customer=other_customer,
    )
    packed.mark_as_placed()
    packed.mark_as_packed()

    assert count_placed_orders() == 1
    assert count_packed_orders() == 1
