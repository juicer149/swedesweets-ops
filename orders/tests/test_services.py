from __future__ import annotations

from datetime import timedelta

import pytest
from django.db.models import ProtectedError

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
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    assert order.status == Order.Status.DRAFT
    assert order.lines.count() == 1
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_create_draft_order_snapshots_customer_details(customer, apple):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=1),
        ],
    )

    assert order.customer_name_snapshot == customer.name
    assert order.customer_email_snapshot == customer.email
    assert order.customer_phone_snapshot == customer.phone_number
    assert order.customer_country_snapshot == customer.country
    assert order.customer_city_snapshot == customer.city
    assert order.customer_address_line_snapshot == customer.address_line

    assert order.customer_name == customer.name
    assert order.customer_email == customer.email
    assert order.customer_phone_number == customer.phone_number
    assert order.customer_country == customer.country
    assert order.customer_city == customer.city
    assert order.customer_address_line == customer.address_line

    assert customer.address_line in order.customer_address
    assert customer.city in order.customer_address


@pytest.mark.django_db
def test_order_customer_display_uses_snapshot_after_customer_changes(customer, apple):
    original_name = customer.name
    original_email = customer.email
    original_phone_number = customer.phone_number
    original_country = customer.country
    original_city = customer.city
    original_address_line = customer.address_line

    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=1),
        ],
    )

    customer.name = "Updated Customer"
    customer.email = "updated@example.fr"
    customer.phone_number = "+33 1 11 22 33 44"
    customer.country = "CH"
    customer.city = "Zürich"
    customer.address_line = "Bahnhofstrasse 1"
    customer.save()

    order.refresh_from_db()

    assert order.customer.name == "Updated Customer"
    assert order.customer.email == "updated@example.fr"
    assert order.customer.phone_number == "+33111223344"
    assert order.customer.country == "CH"
    assert order.customer.city == "Zürich"
    assert order.customer.address_line == "Bahnhofstrasse 1"

    assert order.customer_name == original_name
    assert order.customer_email == original_email
    assert order.customer_phone_number == original_phone_number
    assert order.customer_country == original_country
    assert order.customer_city == original_city
    assert order.customer_address_line == original_address_line

    assert original_address_line in order.customer_address
    assert original_city in order.customer_address
    assert "Bahnhofstrasse" not in order.customer_address
    assert "Zürich" not in order.customer_address


@pytest.mark.django_db
def test_customer_with_order_is_protected_from_delete_but_order_snapshot_remains(
    customer,
    apple,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=1),
        ],
    )

    original_name = customer.name
    original_email = customer.email
    original_phone_number = customer.phone_number
    original_country = customer.country
    original_city = customer.city
    original_address_line = customer.address_line

    with pytest.raises(ProtectedError):
        customer.delete()

    order.refresh_from_db()

    assert order.customer_id == customer.id
    assert order.customer_name == original_name
    assert order.customer_email == original_email
    assert order.customer_phone_number == original_phone_number
    assert order.customer_country == original_country
    assert order.customer_city == original_city
    assert order.customer_address_line == original_address_line


@pytest.mark.django_db
def test_create_draft_order_merges_duplicate_product_lines(customer, apple):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
            OrderLineInput.kg(product=apple, kg="25.0"),
        ],
    )

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 15
    assert line.quantity == 15
    assert line.unit == OrderLine.Unit.STOCK_UNIT


@pytest.mark.django_db
def test_create_draft_order_rejects_empty_order(customer):
    with pytest.raises(
        InvalidOrderOperation, match="order must contain at least one line"
    ):
        create_draft_order(
            customer=customer,
            lines=[],
        )


@pytest.mark.django_db
def test_place_order_places_existing_draft_order(customer, apple, stocked_inventory):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
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
            OrderLineInput.units(product=apple, quantity=10),
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
            OrderLineInput.units(product=apple, quantity=120),
            OrderLineInput.kg(product=banana, kg="25.0"),
        ],
    )

    assert order.status == Order.Status.PLACED

    allocations = list(
        Allocation.objects.select_related("batch", "order_line__product").order_by(
            "batch__batch_id"
        )
    )

    assert [
        (
            allocation.batch.batch_id,
            allocation.order_line.product.sku,
            allocation.quantity,
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
        quantity=100,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(InsufficientStockError) as error:
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.units(product=apple, quantity=120),
            ],
        )

    assert error.value.requested_quantity == 120
    assert error.value.available_quantity == 100
    assert error.value.missing_quantity == 20

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_order_cannot_reserve_expired_stock(customer, apple):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )

    with pytest.raises(InsufficientStockError) as error:
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.units(product=apple, quantity=1),
            ],
        )

    assert error.value.requested_quantity == 1
    assert error.value.available_quantity == 0
    assert error.value.missing_quantity == 1

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_two_placed_orders_do_not_reserve_same_quantity(
    customer, other_customer, apple
):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    first = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=70),
        ],
    )
    second = create_order(
        customer=other_customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=30),
        ],
    )

    assert first.allocations.get().quantity == 70
    assert second.allocations.get().quantity == 30

    with pytest.raises(InsufficientStockError):
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.units(product=apple, quantity=1),
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
            OrderLineInput.units(product=apple, quantity=120),
            OrderLineInput.kg(product=banana, kg="25.0"),
        ],
    )

    order = pack_order(order=order)

    assert order.status == Order.Status.PACKED
    assert order.packed_at is not None

    assert set(Allocation.objects.values_list("status", flat=True)) == {
        Allocation.Status.CONSUMED,
    }

    batches = {
        batch.batch_id: batch for batch in InventoryBatch.objects.order_by("batch_id")
    }

    assert batches["A-001"].quantity == 0
    assert batches["A-001"].status == InventoryBatch.Status.DEPLETED

    assert batches["A-002"].quantity == 30
    assert batches["A-002"].status == InventoryBatch.Status.ACTIVE

    assert batches["B-001"].quantity == 75
    assert batches["B-001"].status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_pack_order_rejects_non_placed_order(customer, apple, stocked_inventory):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    with pytest.raises(InvalidOrderOperation, match="Cannot pack order"):
        pack_order(order=order)


@pytest.mark.django_db
def test_cancel_placed_order_releases_reserved_allocations(
    customer, apple, stocked_inventory
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
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

    assert set(order.allocations.values_list("status", flat=True)) == {
        Allocation.Status.CANCELLED,
    }


@pytest.mark.django_db
def test_cancel_order_rejects_packed_order(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )
    order = pack_order(order=order)

    with pytest.raises(InvalidOrderOperation, match="Cannot cancel order"):
        cancel_order(order=order)


@pytest.mark.django_db
def test_deliver_order_moves_packed_order_to_delivered(
    customer, apple, stocked_inventory
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
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
            OrderLineInput.units(product=apple, quantity=10),
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
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    old_allocation_ids = set(order.allocations.values_list("id", flat=True))

    order = update_placed_order(
        order=order,
        lines=[
            OrderLineInput.units(product=banana, quantity=20),
        ],
    )

    order.refresh_from_db()

    assert order.status == Order.Status.PLACED
    assert order.edited_at is not None
    assert list(order.lines.values_list("product_id", "quantity_in_units")) == [
        (banana.id, 20),
    ]

    assert not Allocation.objects.filter(id__in=old_allocation_ids).exists()
    assert list(order.allocations.values_list("batch__batch_id", "quantity")) == [
        ("B-001", 20),
    ]


@pytest.mark.django_db
def test_update_placed_order_rejects_packed_order(customer, apple, stocked_inventory):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )
    order = pack_order(order=order)

    with pytest.raises(InvalidOrderOperation, match="Only placed orders can be edited"):
        update_placed_order(
            order=order,
            lines=[
                OrderLineInput.units(product=apple, quantity=5),
            ],
        )
