from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from orders.datatypes import BuyerInput
from orders.drafts import (
    OrderDraft,
    ResolvedOrderLine,
)
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from orders.services import (
    cancel_order,
    create_draft_order,
    deliver_order,
    pack_order,
    place_order,
    update_placed_order,
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
def test_update_placed_order_runs_hooks_around_line_replacement(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )
    _create_order_line(
        order=order,
        product=apple,
        quantity=10,
    )

    events: list[
        tuple[str, list[int]]
    ] = []

    def before_replacement(
        *,
        order: Order,
    ) -> None:
        events.append(
            (
                "before",
                list(
                    order.lines.values_list(
                        "quantity_in_units",
                        flat=True,
                    )
                ),
            )
        )

    def preparation(
        *,
        order: Order,
    ) -> None:
        events.append(
            (
                "prepare",
                list(
                    order.lines.values_list(
                        "quantity_in_units",
                        flat=True,
                    )
                ),
            )
        )

    updated = update_placed_order(
        order=order,
        lines=(
            ResolvedOrderLine(
                product=apple,
                quantity_in_units=20,
            ),
        ),
        before_replacement=before_replacement,
        preparation=preparation,
    )

    assert events == [
        (
            "before",
            [10],
        ),
        (
            "prepare",
            [20],
        ),
    ]

    assert updated.status == Order.Status.PLACED
    assert updated.edited_at is not None
    assert list(
        updated.lines.values_list(
            "quantity_in_units",
            flat=True,
        )
    ) == [20]


@pytest.mark.django_db
def test_update_placed_order_rejects_non_placed_before_running_hooks(
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
        quantity=10,
    )

    events: list[str] = []

    def before_replacement(
        *,
        order: Order,
    ) -> None:
        events.append(
            "before"
        )

    def preparation(
        *,
        order: Order,
    ) -> None:
        events.append(
            "prepare"
        )

    with pytest.raises(
        InvalidOrderOperation,
        match="Only placed orders can be edited",
    ):
        update_placed_order(
            order=order,
            lines=(
                ResolvedOrderLine(
                    product=apple,
                    quantity_in_units=20,
                ),
            ),
            before_replacement=before_replacement,
            preparation=preparation,
        )

    assert events == []


@pytest.mark.django_db
def test_update_placed_order_rolls_back_line_replacement_when_preparation_fails(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
        placed_at=timezone.now(),
    )
    original_line = _create_order_line(
        order=order,
        product=apple,
        quantity=10,
    )

    before_called = False

    def before_replacement(
        *,
        order: Order,
    ) -> None:
        nonlocal before_called
        before_called = True

    def preparation(
        *,
        order: Order,
    ) -> None:
        raise RuntimeError(
            "preparation failed"
        )

    with pytest.raises(
        RuntimeError,
        match="preparation failed",
    ):
        update_placed_order(
            order=order,
            lines=(
                ResolvedOrderLine(
                    product=apple,
                    quantity_in_units=20,
                ),
            ),
            before_replacement=before_replacement,
            preparation=preparation,
        )

    assert before_called is True

    assert OrderLine.objects.filter(
        pk=original_line.pk,
        order=order,
        quantity_in_units=10,
    ).exists()

    assert not OrderLine.objects.filter(
        order=order,
        quantity_in_units=20,
    ).exists()


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
def test_cancel_order_runs_injected_preparation_before_transition(
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

    cancelled = cancel_order(
        order=order,
        preparation=preparation,
        reason=Order.CancelReason.CUSTOMER_REQUEST,
        note="  Customer cancelled.  ",
    )

    assert calls == [
        (
            order.pk,
            Order.Status.PLACED,
        )
    ]

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


@pytest.mark.django_db
def test_cancel_order_rejects_non_cancellable_before_running_preparation(
    customer,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PACKED,
        packed_at=timezone.now(),
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
        match="Cannot cancel order",
    ):
        cancel_order(
            order=order,
            preparation=preparation,
        )

    assert called is False


@pytest.mark.django_db
def test_cancel_order_rolls_back_preparation_when_transition_fails(
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

        order.status = Order.Status.DELIVERED

    with pytest.raises(Exception):
        cancel_order(
            order=order,
            preparation=preparation,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 1


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
