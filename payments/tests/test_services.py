from __future__ import annotations

from decimal import Decimal

import pytest

from customers.tests.factories import customer_factory
from orders.models import Order, OrderLine
from payments.models import PaymentAttempt
from payments.services import (
    InvalidPaymentAttempt,
    cancel_pending_payment_attempts_for_order,
    create_payment_attempt,
)
from products.tests.factories import product_factory


def _create_priced_order(
    *,
    amount: Decimal = Decimal("12.50"),
) -> Order:
    customer = customer_factory()
    product = product_factory()

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        currency=Order.Currency.EUR,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    OrderLine.objects.create(
        order=order,
        product=product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
        unit_price_snapshot=amount,
    )

    return order


@pytest.mark.django_db
def test_create_payment_attempt_snapshots_order_amount_and_currency():
    order = _create_priced_order(
        amount=Decimal("12.50"),
    )

    attempt = create_payment_attempt(
        order=order,
    )

    assert attempt.order == order
    assert attempt.status == PaymentAttempt.Status.PENDING
    assert attempt.amount == Decimal("12.50")
    assert attempt.currency == Order.Currency.EUR


@pytest.mark.django_db
def test_create_payment_attempt_rejects_second_pending_attempt():
    order = _create_priced_order()

    create_payment_attempt(
        order=order,
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="already has a pending payment attempt",
    ):
        create_payment_attempt(
            order=order,
        )

    assert (
        PaymentAttempt.objects
        .filter(
            order=order,
            status=PaymentAttempt.Status.PENDING,
        )
        .count()
        == 1
    )


@pytest.mark.django_db
def test_cancel_pending_payment_attempts_for_order():
    order = _create_priced_order()

    attempt = create_payment_attempt(
        order=order,
    )

    cancel_pending_payment_attempts_for_order(
        order=order,
    )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.CANCELLED
    )


@pytest.mark.django_db
def test_cancel_pending_payment_attempts_does_not_change_completed_attempt():
    order = _create_priced_order()

    attempt = PaymentAttempt.objects.create(
        order=order,
        status=PaymentAttempt.Status.SUCCEEDED,
        amount=order.total,
        currency=order.currency,
    )

    cancel_pending_payment_attempts_for_order(
        order=order,
    )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.SUCCEEDED
    )


@pytest.mark.django_db
def test_create_payment_attempt_rejects_unpriced_order():
    customer = customer_factory()
    product = product_factory()

    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        currency=Order.Currency.EUR,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    OrderLine.objects.create(
        order=order,
        product=product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
        unit_price_snapshot=None,
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="unpriced",
    ):
        create_payment_attempt(
            order=order,
        )

    assert PaymentAttempt.objects.count() == 0
