from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.services import create_batch
from orders.models import (
    Allocation,
    Order,
)
from payments.models import PaymentAttempt
from payments.services import InvalidPaymentAttempt
from retail.services import (
    AnonymousBuyerInput,
    InvalidRetailOrder,
    RetailOrderLineInput,
    create_pending_retail_order,
    fail_retail_payment,
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

    batch = create_batch(
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

    return checkout, attempt, batch


@pytest.mark.django_db
def test_fail_retail_payment_marks_attempt_failed_and_releases_hold():
    checkout, attempt, batch = _create_checkout_with_payment_attempt()

    allocation = checkout.order.allocations.get()

    assert allocation.status == Allocation.Status.RESERVED
    assert allocation.reserved_until is not None

    failed_attempt = fail_retail_payment(
        attempt=attempt,
    )

    checkout.order.refresh_from_db()
    allocation.refresh_from_db()
    batch.refresh_from_db()

    assert (
        failed_attempt.status
        == PaymentAttempt.Status.FAILED
    )
    assert (
        checkout.order.status
        == Order.Status.DRAFT
    )

    assert (
        allocation.status
        == Allocation.Status.CANCELLED
    )

    assert batch.quantity == 10


@pytest.mark.django_db
def test_failed_retail_payment_can_be_retried():
    checkout, attempt, _batch = _create_checkout_with_payment_attempt()

    fail_retail_payment(
        attempt=attempt,
    )

    second_attempt = start_retail_payment(
        checkout=checkout,
    )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.FAILED
    )
    assert (
        second_attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert attempt.pk != second_attempt.pk

    active_allocations = (
        checkout.order.allocations
        .filter(
            status=Allocation.Status.RESERVED,
        )
    )

    assert active_allocations.count() == 1
    assert active_allocations.get().reserved_until is not None


@pytest.mark.django_db
def test_cancelled_payment_attempt_cannot_fail_later():
    checkout, first_attempt, _batch = (
        _create_checkout_with_payment_attempt()
    )

    second_attempt = start_retail_payment(
        checkout=checkout,
    )

    first_attempt.refresh_from_db()

    assert (
        first_attempt.status
        == PaymentAttempt.Status.CANCELLED
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="only pending",
    ):
        fail_retail_payment(
            attempt=first_attempt,
        )

    second_attempt.refresh_from_db()

    assert (
        second_attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        checkout.order.allocations
        .filter(
            status=Allocation.Status.RESERVED,
        )
        .count()
        == 1
    )


@pytest.mark.django_db
def test_successful_payment_attempt_cannot_fail_later():
    checkout, attempt, _batch = _create_checkout_with_payment_attempt()

    attempt.status = PaymentAttempt.Status.SUCCEEDED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="only pending",
    ):
        fail_retail_payment(
            attempt=attempt,
        )

    allocation = checkout.order.allocations.get()

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )


@pytest.mark.django_db
def test_fail_retail_payment_rejects_non_draft_order_before_releasing_hold():
    checkout, attempt, _batch = _create_checkout_with_payment_attempt()

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
        InvalidRetailOrder,
        match="only draft retail orders can fail payment",
    ):
        fail_retail_payment(
            attempt=attempt,
        )

    attempt.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert (
        allocation.reserved_until
        == original_reserved_until
    )
