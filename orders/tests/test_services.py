from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.services import create_batch
from orders.datatypes import BuyerInput
from orders.drafts import (
    OrderDraft,
    ResolvedOrderLine,
)
from orders.errors import InvalidOrderOperation
from orders.models import (
    Allocation,
    Order,
    OrderLine,
)
from orders.services import (
    cancel_order,
    create_draft_order,
    deliver_order,
    pack_order,
    place_order,
)


TODAY = timezone.localdate()


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
def test_place_order_runs_injected_preparation_before_transition(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    _create_order_line(
        order=order,
        product=apple,
        quantity=1,
    )

    calls: list[tuple[int, str]] = []

    def preparation(
        *,
        order: Order,
    ) -> None:
        calls.append(
            (
                order.pk,
                order.status,
            )
        )

    placed = place_order(
        order=order,
        preparation=preparation,
    )

    assert calls == [
        (
            order.pk,
            Order.Status.DRAFT,
        )
    ]
    assert placed.status == Order.Status.PLACED
    assert placed.placed_at is not None


@pytest.mark.django_db
def test_place_order_uses_fresh_persisted_order(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    _create_order_line(
        order=order,
        product=apple,
        quantity=1,
    )

    stale_order = Order.objects.get(
        pk=order.pk,
    )

    seen_statuses: list[str] = []

    def preparation(
        *,
        order: Order,
    ) -> None:
        seen_statuses.append(
            order.status
        )

    place_order(
        order=stale_order,
        preparation=preparation,
    )

    assert seen_statuses == [
        Order.Status.DRAFT,
    ]


@pytest.mark.django_db
def test_place_order_rejects_non_draft_before_running_preparation(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
    )

    called = False

    def preparation(
        *,
        order: Order,
    ) -> None:
        nonlocal called
        called = True

    with pytest.raises(
        InvalidOrderOperation,
        match="Only draft orders can be placed",
    ):
        place_order(
            order=order,
            preparation=preparation,
        )

    assert called is False


@pytest.mark.django_db
def test_place_order_rolls_back_preparation_when_transition_fails(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_order_line(
        order=order,
        product=apple,
        quantity=1,
    )

    def preparation(
        *,
        order: Order,
    ) -> None:
        line = order.lines.get()
        line.quantity = 2
        line.quantity_in_units = 2
        line.save(
            update_fields=[
                "quantity",
                "quantity_in_units",
            ]
        )

        order.status = Order.Status.PACKED

    with pytest.raises(Exception):
        place_order(
            order=order,
            preparation=preparation,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 1


@pytest.mark.django_db
def test_pack_order_runs_injected_preparation_before_transition(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )

    calls: list[tuple[int, str]] = []

    def preparation(
        *,
        order: Order,
    ) -> None:
        calls.append(
            (
                order.pk,
                order.status,
            )
        )

    packed = pack_order(
        order=order,
        preparation=preparation,
    )

    assert calls == [
        (
            order.pk,
            Order.Status.PLACED,
        )
    ]
    assert packed.status == Order.Status.PACKED
    assert packed.packed_at is not None


@pytest.mark.django_db
def test_pack_order_rejects_non_placed_before_running_preparation(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    called = False

    def preparation(
        *,
        order: Order,
    ) -> None:
        nonlocal called
        called = True

    with pytest.raises(
        InvalidOrderOperation,
        match="Cannot pack order",
    ):
        pack_order(
            order=order,
            preparation=preparation,
        )

    assert called is False


@pytest.mark.django_db
def test_pack_order_rolls_back_preparation_when_transition_fails(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )
    line = _create_order_line(
        order=order,
        product=apple,
        quantity=1,
    )

    def preparation(
        *,
        order: Order,
    ) -> None:
        line = order.lines.get()
        line.quantity = 2
        line.quantity_in_units = 2
        line.save(
            update_fields=[
                "quantity",
                "quantity_in_units",
            ]
        )

        order.status = Order.Status.DRAFT

    with pytest.raises(Exception):
        pack_order(
            order=order,
            preparation=preparation,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 1


@pytest.mark.django_db
def test_cancel_order_releases_existing_reservations(
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

    cancelled = cancel_order(
        order=order,
        reason=(
            Order.CancelReason.CUSTOMER_REQUEST
        ),
        note="  Customer cancelled.  ",
    )

    cancelled.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        cancelled.status
        == Order.Status.CANCELLED
    )
    assert (
        cancelled.cancel_reason
        == Order.CancelReason.CUSTOMER_REQUEST
    )
    assert (
        cancelled.cancel_note
        == "Customer cancelled."
    )
    assert (
        allocation.status
        == Allocation.Status.CANCELLED
    )


@pytest.mark.django_db
def test_cancel_order_rejects_packed_order(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PACKED,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="Cannot cancel order",
    ):
        cancel_order(
            order=order,
        )


@pytest.mark.django_db
def test_deliver_order_moves_packed_order_to_delivered(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PACKED,
        packed_at=timezone.now(),
    )

    delivered = deliver_order(
        order=order,
    )

    delivered.refresh_from_db()

    assert (
        delivered.status
        == Order.Status.DELIVERED
    )
    assert delivered.delivered_at is not None


@pytest.mark.django_db
def test_deliver_order_rejects_placed_order(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )

    with pytest.raises(
        Exception,
        match="Cannot transition",
    ):
        deliver_order(
            order=order,
        )


@pytest.mark.django_db
def test_create_draft_order_persists_resolved_order_data(
    customer,
    apple,
):
    order = create_draft_order(
        draft=OrderDraft(
            channel=Order.Channel.BUSINESS,
            currency=Order.Currency.EUR,
            customer=customer,
            buyer=BuyerInput(
                name="Resolved Buyer",
                email="buyer@example.com",
                phone_number="+33123456789",
                country="FR",
                postal_code="74000",
                city="Annecy",
                address_line="1 Test Street",
            ),
            lines=(
                ResolvedOrderLine(
                    product=apple,
                    quantity_in_units=3,
                    unit_price_snapshot=Decimal("12.50"),
                ),
            ),
        ),
    )

    line = order.lines.get()

    assert order.status == Order.Status.DRAFT
    assert order.channel == Order.Channel.BUSINESS
    assert order.currency == Order.Currency.EUR
    assert order.customer == customer
    assert order.buyer_name == "Resolved Buyer"

    assert line.product == apple
    assert line.quantity == 3
    assert line.quantity_in_units == 3
    assert (
        line.unit_price_snapshot
        == Decimal("12.50")
    )


@pytest.mark.django_db
def test_create_draft_order_rejects_empty_resolved_draft(
    customer,
):
    with pytest.raises(
        InvalidOrderOperation,
        match="order must contain at least one line",
    ):
        create_draft_order(
            draft=OrderDraft(
                channel=Order.Channel.BUSINESS,
                currency=Order.Currency.EUR,
                customer=customer,
                buyer=BuyerInput(
                    name="Resolved Buyer",
                    email="buyer@example.com",
                    phone_number="+33123456789",
                    country="FR",
                    postal_code="74000",
                    city="Annecy",
                    address_line="1 Test Street",
                ),
                lines=(),
            ),
        )
