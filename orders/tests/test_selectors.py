from __future__ import annotations

import pytest

from orders.datatypes import OrderLineInput
from orders.models import Order
from orders.selectors import (
    count_packed_orders,
    count_placed_orders,
    get_packaging_list,
    get_packed_lines,
    list_orders,
    list_packed_orders_for_dashboard,
    list_placed_orders_for_dashboard,
)
from orders.services import create_draft_order, create_order, pack_order


@pytest.mark.django_db
def test_packaging_list_comes_from_reserved_allocations(
    apple,
    banana,
    customer,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=120),
            OrderLineInput.kg(product=banana, kg="25.0"),
        ],
    )

    pick_lines = get_packaging_list(order=order)

    assert [
        (line.sku, line.batch_id, line.location, line.boxes)
        for line in pick_lines
    ] == [
        ("SS-001", "A-001", "Shelf A1", 100),
        ("SS-001", "A-002", "Shelf A2", 20),
        ("SS-002", "B-001", "Shelf B1", 5),
    ]


@pytest.mark.django_db
def test_packed_lines_come_from_consumed_allocations(
    apple,
    banana,
    customer,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=120),
            OrderLineInput.kg(product=banana, kg="25.0"),
        ],
    )

    order = pack_order(order=order)
    pick_lines = get_packed_lines(order=order)

    assert [
        (line.sku, line.batch_id, line.location, line.boxes)
        for line in pick_lines
    ] == [
        ("SS-001", "A-001", "Shelf A1", 100),
        ("SS-001", "A-002", "Shelf A2", 20),
        ("SS-002", "B-001", "Shelf B1", 5),
    ]


@pytest.mark.django_db
def test_list_orders_filters_by_status(customer, other_customer, apple, stocked_inventory):
    placed = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    draft = create_draft_order(
        customer=other_customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    orders = list(list_orders(status=Order.Status.PLACED))

    assert placed in orders
    assert draft not in orders


@pytest.mark.django_db
def test_list_orders_annotates_total_boxes(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    listed = list_orders().get(pk=order.pk)

    assert listed.total_boxes == 10


@pytest.mark.django_db
def test_list_placed_orders_for_dashboard_returns_only_placed_orders(
    customer,
    other_customer,
    apple,
    stocked_inventory,
):
    placed = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    packed = create_order(
        customer=other_customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    pack_order(order=packed)

    rows = list(list_placed_orders_for_dashboard(limit=3))

    assert placed in rows
    assert packed not in rows


@pytest.mark.django_db
def test_list_packed_orders_for_dashboard_returns_only_packed_orders(
    customer,
    other_customer,
    apple,
    stocked_inventory,
):
    placed = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    packed = create_order(
        customer=other_customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    packed = pack_order(order=packed)

    rows = list(list_packed_orders_for_dashboard(limit=3))

    assert packed in rows
    assert placed not in rows


@pytest.mark.django_db
def test_count_placed_and_packed_orders(customer, other_customer, apple, stocked_inventory):
    create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    packed = create_order(
        customer=other_customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    pack_order(order=packed)

    assert count_placed_orders() == 1
    assert count_packed_orders() == 1
