from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.services import create_batch
from orders.errors import InvalidOrderOperation
from orders.models import (
    Allocation,
    Order,
)
from payments.models import PaymentAttempt
from payments.services import InvalidPaymentAttempt
from retail.services import (
    AnonymousBuyerInput,
    RetailOrderLineInput,
    complete_retail_payment,
    create_pending_retail_order,
    start_retail_payment,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_offer_factory,
)


def _create_checkout_with_payment_attempt():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=10,
        best_before=(
            timezone.localdate()
            + timedelta(days=60)
        ),
        location="Shelf A1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    attempt = start_retail_payment(
        checkout=checkout,
    )

    return checkout, attempt


@pytest.mark.django_db
def test_complete_retail_payment_places_order_and_makes_reservation_permanent():
    checkout, attempt = _create_checkout_with_payment_attempt()

    order = complete_retail_payment(
        attempt=attempt,
    )

    attempt.refresh_from_db()

    allocation = (
        order.allocations
        .get()
    )

    assert order.status == Order.Status.PLACED
    assert order.placed_at is not None

    assert (
        attempt.status
        == PaymentAttempt.Status.SUCCEEDED
    )

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is None

    assert allocation.batch.quantity == 10


@pytest.mark.django_db
def test_complete_retail_payment_rejects_cancelled_attempt():
    checkout, first_attempt = _create_checkout_with_payment_attempt()

    second_attempt = start_retail_payment(
        checkout=checkout,
    )

    first_attempt.refresh_from_db()

    assert (
        first_attempt.status
        == PaymentAttempt.Status.CANCELLED
    )
    assert (
        second_attempt.status
        == PaymentAttempt.Status.PENDING
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="only pending",
    ):
        complete_retail_payment(
            attempt=first_attempt,
        )

    checkout.order.refresh_from_db()
    second_attempt.refresh_from_db()

    assert (
        checkout.order.status
        == Order.Status.DRAFT
    )
    assert (
        second_attempt.status
        == PaymentAttempt.Status.PENDING
    )


@pytest.mark.django_db
def test_complete_retail_payment_rejects_expired_reservations():
    checkout, attempt = _create_checkout_with_payment_attempt()

    checkout.order.allocations.update(
        reserved_until=(
            timezone.now()
            - timedelta(seconds=1)
        ),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="no active payment reservations",
    ):
        complete_retail_payment(
            attempt=attempt,
        )

    checkout.order.refresh_from_db()
    attempt.refresh_from_db()

    allocation = checkout.order.allocations.get()

    assert (
        checkout.order.status
        == Order.Status.DRAFT
    )
    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert allocation.reserved_until is not None


@pytest.mark.django_db
def test_complete_retail_payment_is_atomic_when_order_placement_fails():
    checkout, attempt = _create_checkout_with_payment_attempt()

    allocation = checkout.order.allocations.get()
    original_reserved_until = allocation.reserved_until

    checkout.order.status = Order.Status.PLACED
    checkout.order.placed_at = timezone.now()
    checkout.order.save(
        update_fields=[
            "status",
            "placed_at",
        ]
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="Only draft orders can be placed",
    ):
        complete_retail_payment(
            attempt=attempt,
        )

    attempt.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        allocation.reserved_until
        == original_reserved_until
    )
