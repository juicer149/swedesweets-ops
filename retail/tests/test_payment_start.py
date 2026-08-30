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


def _create_checkout():
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

    return create_pending_retail_order(
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


@pytest.mark.django_db
def test_start_retail_payment_creates_pending_payment_attempt():
    checkout = _create_checkout()

    attempt = start_retail_payment(
        checkout=checkout,
    )

    assert attempt.order_id == checkout.order_id
    assert attempt.status == PaymentAttempt.Status.PENDING
    assert attempt.amount == Decimal("25.00")
    assert attempt.currency == Order.Currency.EUR

    checkout.order.refresh_from_db()

    assert (
        checkout.order.status
        == Order.Status.DRAFT
    )

    allocation = checkout.order.allocations.get()

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is not None


@pytest.mark.django_db
def test_start_retail_payment_rejects_existing_pending_attempt():
    checkout = _create_checkout()

    first_attempt = start_retail_payment(
        checkout=checkout,
    )

    allocation = checkout.order.allocations.get()
    original_reserved_until = allocation.reserved_until

    with pytest.raises(
        InvalidRetailOrder,
        match="already has a pending payment attempt",
    ):
        start_retail_payment(
            checkout=checkout,
        )

    first_attempt.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        first_attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        PaymentAttempt.objects
        .filter(order=checkout.order)
        .count()
        == 1
    )

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert (
        allocation.reserved_until
        == original_reserved_until
    )


@pytest.mark.django_db
def test_new_retail_payment_can_start_after_previous_attempt_failed():
    checkout = _create_checkout()

    first_attempt = start_retail_payment(
        checkout=checkout,
    )

    first_allocation = checkout.order.allocations.get()

    fail_retail_payment(
        attempt=first_attempt,
    )

    first_attempt.refresh_from_db()
    first_allocation.refresh_from_db()

    assert (
        first_attempt.status
        == PaymentAttempt.Status.FAILED
    )
    assert (
        first_allocation.status
        == Allocation.Status.CANCELLED
    )

    second_attempt = start_retail_payment(
        checkout=checkout,
    )

    second_attempt.refresh_from_db()

    assert second_attempt.pk != first_attempt.pk
    assert (
        second_attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        PaymentAttempt.objects
        .filter(order=checkout.order)
        .count()
        == 2
    )

    active_allocations = (
        checkout.order.allocations
        .filter(
            status=Allocation.Status.RESERVED,
        )
    )

    assert active_allocations.count() == 1

    second_allocation = active_allocations.get()

    assert (
        second_allocation.pk
        != first_allocation.pk
    )
    assert second_allocation.reserved_until is not None
