from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.errors import InsufficientStockError
from inventory.services import create_batch
from orders.models import (
    Allocation,
    Order,
)
from payments.models import PaymentAttempt
from retail.services import (
    AnonymousBuyerInput,
    RetailOrderLineInput,
    create_pending_retail_order,
    start_retail_payment,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_start_retail_payment_creates_pending_payment_attempt():
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

    assert attempt.order_id == checkout.order_id
    assert attempt.status == PaymentAttempt.Status.PENDING
    assert attempt.amount == Decimal("25.00")
    assert attempt.currency == Order.Currency.EUR

    checkout.order.refresh_from_db()

    assert checkout.order.status == Order.Status.DRAFT

    allocation = checkout.order.allocations.get()

    assert allocation.status == Allocation.Status.RESERVED
    assert allocation.reserved_until is not None


@pytest.mark.django_db
def test_starting_retail_payment_again_replaces_pending_attempt():
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

    first_attempt = start_retail_payment(
        checkout=checkout,
    )

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

    assert first_attempt.pk != second_attempt.pk

    assert (
        PaymentAttempt.objects
        .filter(
            order=checkout.order,
            status=PaymentAttempt.Status.PENDING,
        )
        .count()
        == 1
    )


@pytest.mark.django_db
def test_failed_retail_payment_start_rolls_back_attempt_replacement():
    retail_postal_area_factory()

    first_product = retail_product_factory(
        name="Product A",
    )
    second_product = retail_product_factory(
        name="Product B",
    )

    first_offer = retail_product_offer_factory(
        product=first_product,
        enabled=True,
        price=Decimal("12.50"),
    )
    second_offer = retail_product_offer_factory(
        product=second_product,
        enabled=True,
        price=Decimal("8.50"),
    )

    first_batch = create_batch(
        batch_id="A-001",
        product=first_product,
        quantity=10,
        best_before=(
            timezone.localdate()
            + timedelta(days=60)
        ),
        location="Shelf A1",
    )

    second_batch = create_batch(
        batch_id="B-001",
        product=second_product,
        quantity=10,
        best_before=(
            timezone.localdate()
            + timedelta(days=60)
        ),
        location="Shelf B1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=first_offer.pk,
                quantity=4,
            ),
            RetailOrderLineInput(
                product_offer_id=second_offer.pk,
                quantity=2,
            ),
        ],
    )

    first_attempt = start_retail_payment(
        checkout=checkout,
    )

    first_allocations = list(
        checkout.order.allocations
        .filter(
            status=Allocation.Status.RESERVED,
        )
        .order_by("id")
    )

    assert len(first_allocations) == 2

    second_batch.quantity = 1
    second_batch.save(
        update_fields=[
            "quantity",
        ]
    )

    with pytest.raises(
        InsufficientStockError,
    ):
        start_retail_payment(
            checkout=checkout,
        )

    first_attempt.refresh_from_db()

    assert (
        first_attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        PaymentAttempt.objects
        .filter(
            order=checkout.order,
            status=PaymentAttempt.Status.PENDING,
        )
        .count()
        == 1
    )

    for allocation in first_allocations:
        allocation.refresh_from_db()

        assert (
            allocation.status
            == Allocation.Status.RESERVED
        )

    first_batch.refresh_from_db()
    second_batch.refresh_from_db()
