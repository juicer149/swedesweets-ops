from __future__ import annotations

import pytest

from inventory.errors import InsufficientStockError
from inventory.models import InventoryBatch
from inventory.services import create_batch
from orders.datatypes import OrderLineInput
from orders.errors import InvalidOrderOperation
from orders.models import Allocation, Order, OrderLine
from orders.services import (
    cancel_order,
    create_draft_order,
    create_order,
    deliver_order,
    pack_order,
    place_order,
    update_placed_order,
)
from orders.tests.conftest import TODAY


@pytest.mark.django_db
def test_create_draft_order_creates_lines_but_does_not_reserve_stock(
    apple,
    customer,
    stocked_inventory,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    assert order.status == Order.Status.DRAFT
    assert order.lines.count() == 1
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_create_draft_order_merges_duplicate_product_lines(customer, apple):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
            OrderLineInput.kg(product=apple, kg="25.0"),
        ],
    )

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_boxes == 15
    assert line.quantity == 15
    assert line.unit == OrderLine.Unit.BOXES


@pytest.mark.django_db
def test_create_draft_order_rejects_empty_order(customer):
    with pytest.raises(InvalidOrderOperation, match="order must contain at least one line"):
        create_draft_order(
            customer=customer,
            lines=[],
        )


@pytest.mark.django_db
def test_place_order_places_existing_draft_order(customer, apple, stocked_inventory):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    order = place_order(order=order)

    assert order.status == Order.Status.PLACED
    assert order.placed_at is not None
    assert Allocation.objects.count() == 1


@pytest.mark.django_db
def test_place_order_rejects_non_draft_order(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    with pytest.raises(InvalidOrderOperation, match="Only draft orders can be placed"):
        place_order(order=order)


@pytest.mark.django_db
def test_create_order_places_order_and_creates_fefo_allocations(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=120),
            OrderLineInput.kg(product=banana, kg="25.0"),
        ],
    )

    assert order.status == Order.Status.PLACED

    allocations = list(
        Allocation.objects
        .select_related("batch", "order_line__product")
        .order_by("batch__batch_id")
    )

    assert [
        (
            allocation.batch.batch_id,
            allocation.order_line.product.sku,
            allocation.boxes,
            allocation.status,
        )
        for allocation in allocations
    ] == [
        ("A-001", "SS-001", 100, Allocation.Status.RESERVED),
        ("A-002", "SS-001", 20, Allocation.Status.RESERVED),
        ("B-001", "SS-002", 5, Allocation.Status.RESERVED),
    ]


@pytest.mark.django_db
def test_order_cannot_reserve_more_than_available_stock(customer, apple):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=TODAY.replace(month=6, day=1),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(InsufficientStockError) as error:
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.boxes(product=apple, boxes=120),
            ],
        )

    assert error.value.requested_boxes == 120
    assert error.value.available_boxes == 100
    assert error.value.missing_boxes == 20

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_two_placed_orders_do_not_reserve_same_boxes(customer, other_customer, apple):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=TODAY.replace(month=6, day=1),
        location="Shelf A1",
        today=TODAY,
    )

    first = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=70),
        ],
    )
    second = create_order(
        customer=other_customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=30),
        ],
    )

    assert first.allocations.get().boxes == 70
    assert second.allocations.get().boxes == 30

    with pytest.raises(InsufficientStockError):
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.boxes(product=apple, boxes=1),
            ],
        )

@pytest.mark.django_db
def test_pack_order_consumes_allocations_and_reduces_physical_stock(
    customer,
    apple,
    banana,
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

    assert order.status == Order.Status.PACKED
    assert order.packed_at is not None

    assert set(
        Allocation.objects.values_list("status", flat=True)
    ) == {
        Allocation.Status.CONSUMED,
    }

    batches = {
        batch.batch_id: batch
        for batch in InventoryBatch.objects.order_by("batch_id")
    }

    assert batches["A-001"].boxes == 0
    assert batches["A-001"].status == InventoryBatch.Status.DEPLETED

    assert batches["A-002"].boxes == 30
    assert batches["A-002"].status == InventoryBatch.Status.ACTIVE

    assert batches["B-001"].boxes == 75
    assert batches["B-001"].status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_pack_order_rejects_non_placed_order(customer, apple, stocked_inventory):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    with pytest.raises(InvalidOrderOperation, match="Cannot pack order"):
        pack_order(order=order)


@pytest.mark.django_db
def test_cancel_placed_order_releases_reserved_allocations(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    order = cancel_order(
        order=order,
        reason=Order.CancelReason.CUSTOMER_REQUEST,
        note="  Customer cancelled.  ",
    )

    order.refresh_from_db()

    assert order.status == Order.Status.CANCELLED
    assert order.cancel_reason == Order.CancelReason.CUSTOMER_REQUEST
    assert order.cancel_note == "Customer cancelled."

    assert set(
        order.allocations.values_list("status", flat=True)
    ) == {
        Allocation.Status.CANCELLED,
    }


@pytest.mark.django_db
def test_cancel_order_rejects_packed_order(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    order = pack_order(order=order)

    with pytest.raises(InvalidOrderOperation, match="Cannot cancel order"):
        cancel_order(order=order)


@pytest.mark.django_db
def test_deliver_order_moves_packed_order_to_delivered(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    order = pack_order(order=order)

    order = deliver_order(order=order)
    order.refresh_from_db()

    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None


@pytest.mark.django_db
def test_deliver_order_rejects_placed_order(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    with pytest.raises(Exception, match="Cannot transition"):
        deliver_order(order=order)


@pytest.mark.django_db
def test_update_placed_order_rebuilds_lines_and_reservations(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )

    old_allocation_ids = set(order.allocations.values_list("id", flat=True))

    order = update_placed_order(
        order=order,
        lines=[
            OrderLineInput.boxes(product=banana, boxes=20),
        ],
    )

    order.refresh_from_db()

    assert order.status == Order.Status.PLACED
    assert order.edited_at is not None
    assert list(order.lines.values_list("product_id", "quantity_in_boxes")) == [
        (banana.id, 20),
    ]

    assert not Allocation.objects.filter(id__in=old_allocation_ids).exists()
    assert list(order.allocations.values_list("batch__batch_id", "boxes")) == [
        ("B-001", 20),
    ]


@pytest.mark.django_db
def test_update_placed_order_rejects_packed_order(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.boxes(product=apple, boxes=10),
        ],
    )
    order = pack_order(order=order)

    with pytest.raises(InvalidOrderOperation, match="Only placed orders can be edited"):
        update_placed_order(
            order=order,
            lines=[
                OrderLineInput.boxes(product=apple, boxes=5),
            ],
        )
