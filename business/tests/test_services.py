from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from business.policies import (
    prepare_business_order_for_placement,
)
from business.services import (
    create_draft_order,
    create_order,
    place_order,
    update_placed_order,
)
from business.tests.conftest import TODAY
from inventory.errors import InsufficientStockError
from inventory.services import create_batch
from orders.datatypes import OrderLineInput
from orders.errors import InvalidOrderOperation
from orders.models import (
    Allocation,
    Order,
    OrderLine,
)


@pytest.mark.django_db
def test_create_order_places_business_order_and_reserves_fefo(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=120,
            ),
            OrderLineInput.kg(
                product=banana,
                kg="25.0",
            ),
        ],
    )

    assert order.channel == Order.Channel.BUSINESS
    assert order.status == Order.Status.PLACED

    allocations = list(
        order.allocations
        .select_related(
            "batch",
            "order_line__product",
        )
        .order_by(
            "batch__batch_id",
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
        (
            "A-001",
            "SS-001",
            100,
            Allocation.Status.RESERVED,
        ),
        (
            "A-002",
            "SS-001",
            20,
            Allocation.Status.RESERVED,
        ),
        (
            "B-001",
            "SS-002",
            5,
            Allocation.Status.RESERVED,
        ),
    ]


@pytest.mark.django_db
def test_create_order_rolls_back_when_stock_is_insufficient(
    customer,
    apple,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(
        InsufficientStockError,
    ) as error:
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.units(
                    product=apple,
                    quantity=120,
                ),
            ],
        )

    assert (
        error.value.requested_quantity
        == 120
    )
    assert (
        error.value.available_quantity
        == 100
    )
    assert (
        error.value.missing_quantity
        == 20
    )

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_create_order_does_not_use_expired_stock(
    customer,
    apple,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )

    with pytest.raises(
        InsufficientStockError,
    ):
        create_order(
            customer=customer,
            lines=[
                OrderLineInput.units(
                    product=apple,
                    quantity=1,
                ),
            ],
        )

    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_create_draft_order_creates_business_draft_without_reservations(
    customer,
    apple,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
        ],
    )

    assert order.channel == Order.Channel.BUSINESS
    assert order.status == Order.Status.DRAFT
    assert order.customer == customer

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 10
    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_create_draft_order_snapshots_business_customer(
    customer,
    apple,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=1,
            ),
        ],
    )

    assert order.buyer_name == customer.name
    assert order.buyer_email == customer.email
    assert (
        order.buyer_phone_number
        == customer.phone_number
    )
    assert order.buyer_country == customer.country
    assert order.buyer_city == customer.city
    assert (
        order.buyer_address_line
        == customer.address_line
    )


@pytest.mark.django_db
def test_create_draft_order_merges_duplicate_business_product_lines(
    customer,
    apple,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
            OrderLineInput.kg(
                product=apple,
                kg="25.0",
            ),
        ],
    )

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 15
    assert line.quantity == 15
    assert line.unit == OrderLine.Unit.STOCK_UNIT


@pytest.mark.django_db
def test_create_draft_order_rejects_empty_business_order(
    customer,
):
    with pytest.raises(
        InvalidOrderOperation,
        match="order must contain at least one line",
    ):
        create_draft_order(
            customer=customer,
            lines=[],
        )


@pytest.mark.django_db
def test_place_order_places_existing_business_draft(
    customer,
    apple,
    stocked_inventory,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
        ],
    )

    placed = place_order(
        order=order,
    )

    assert placed.status == Order.Status.PLACED
    assert placed.placed_at is not None

    allocation = placed.allocations.get()

    assert allocation.quantity == 10
    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is None


@pytest.mark.django_db
def test_place_order_rejects_non_draft_business_order(
    customer,
    apple,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
        ],
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="Only draft orders can be placed",
    ):
        place_order(
            order=order,
        )


@pytest.mark.django_db
def test_business_policy_rejects_retail_order(
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
        status=Order.Status.DRAFT,
    )
    OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="requires a business order",
    ):
        prepare_business_order_for_placement(
            order=order,
        )


@pytest.mark.django_db
def test_unexpired_retail_hold_reduces_business_availability(
    other_customer,
    apple,
):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )

    retail_order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
        status=Order.Status.DRAFT,
    )
    retail_line = OrderLine.objects.create(
        order=retail_order,
        product=apple,
        quantity=7,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=7,
    )

    Allocation.objects.create(
        order=retail_order,
        order_line=retail_line,
        batch=batch,
        quantity=7,
        reserved_until=(
            timezone.now()
            + timedelta(minutes=35)
        ),
    )

    with pytest.raises(
        InsufficientStockError,
    ) as error:
        create_order(
            customer=other_customer,
            lines=[
                OrderLineInput.units(
                    product=apple,
                    quantity=4,
                ),
            ],
        )

    assert (
        error.value.requested_quantity
        == 4
    )
    assert (
        error.value.available_quantity
        == 3
    )
    assert (
        error.value.missing_quantity
        == 1
    )


@pytest.mark.django_db
def test_expired_retail_hold_does_not_reduce_business_availability(
    customer,
    apple,
):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )

    retail_order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
        status=Order.Status.DRAFT,
    )
    retail_line = OrderLine.objects.create(
        order=retail_order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )

    Allocation.objects.create(
        order=retail_order,
        order_line=retail_line,
        batch=batch,
        quantity=10,
        reserved_until=(
            timezone.now()
            - timedelta(seconds=1)
        ),
    )

    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
        ],
    )

    assert (
        order.allocations.get().quantity
        == 10
    )


@pytest.mark.django_db
def test_cancelled_retail_hold_does_not_reduce_business_availability(
    customer,
    apple,
):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )

    retail_order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
        status=Order.Status.DRAFT,
    )
    retail_line = OrderLine.objects.create(
        order=retail_order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )

    allocation = Allocation.objects.create(
        order=retail_order,
        order_line=retail_line,
        batch=batch,
        quantity=10,
        reserved_until=(
            timezone.now()
            + timedelta(minutes=35)
        ),
    )
    allocation.cancel()

    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
        ],
    )

    assert (
        order.allocations.get().quantity
        == 10
    )


@pytest.mark.django_db
def test_update_placed_order_rebuilds_business_reservations(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=10,
            ),
        ],
    )

    previous_allocation_ids = set(
        order.allocations.values_list(
            "id",
            flat=True,
        )
    )

    updated = update_placed_order(
        order=order,
        lines=[
            OrderLineInput.units(
                product=banana,
                quantity=20,
            ),
        ],
    )

    updated.refresh_from_db()

    assert updated.status == Order.Status.PLACED
    assert updated.edited_at is not None

    assert list(
        updated.lines.values_list(
            "product_id",
            "quantity_in_units",
        )
    ) == [
        (
            banana.id,
            20,
        )
    ]

    assert not Allocation.objects.filter(
        id__in=previous_allocation_ids,
    ).exists()

    assert list(
        updated.allocations.values_list(
            "batch__batch_id",
            "quantity",
        )
    ) == [
        (
            "B-001",
            20,
        )
    ]


@pytest.mark.django_db
def test_update_placed_order_rejects_non_placed_order(
    customer,
    apple,
):
    order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=1,
            ),
        ],
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="Only placed orders can be edited",
    ):
        update_placed_order(
            order=order,
            lines=[
                OrderLineInput.units(
                    product=apple,
                    quantity=2,
                ),
            ],
        )
