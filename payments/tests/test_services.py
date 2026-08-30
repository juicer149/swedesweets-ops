from __future__ import annotations

from decimal import Decimal

import pytest

from customers.tests.factories import customer_factory
from orders.models import Order, OrderLine
from payments.contracts import HostedPaymentSession
from payments.models import PaymentAttempt
from payments.services import (
    InvalidPaymentAttempt,
    cancel_pending_payment_attempts_for_order,
    create_hosted_payment_session,
    create_payment_attempt,
    mark_payment_attempt_failed,
    mark_payment_attempt_succeeded,
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


@pytest.mark.django_db
def test_mark_payment_attempt_succeeded():
    order = _create_priced_order()

    attempt = create_payment_attempt(
        order=order,
    )

    succeeded = mark_payment_attempt_succeeded(
        attempt=attempt,
    )

    assert (
        succeeded.status
        == PaymentAttempt.Status.SUCCEEDED
    )


@pytest.mark.django_db
def test_cancelled_payment_attempt_cannot_succeed():
    order = _create_priced_order()

    attempt = create_payment_attempt(
        order=order,
    )

    cancel_pending_payment_attempts_for_order(
        order=order,
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="only pending",
    ):
        mark_payment_attempt_succeeded(
            attempt=attempt,
        )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.CANCELLED
    )


@pytest.mark.django_db
def test_mark_payment_attempt_failed():
    order = _create_priced_order()

    attempt = create_payment_attempt(
        order=order,
    )

    failed = mark_payment_attempt_failed(
        attempt=attempt,
    )

    assert (
        failed.status
        == PaymentAttempt.Status.FAILED
    )


@pytest.mark.django_db
def test_cancelled_payment_attempt_cannot_fail():
    order = _create_priced_order()

    attempt = create_payment_attempt(
        order=order,
    )

    cancel_pending_payment_attempts_for_order(
        order=order,
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="only pending",
    ):
        mark_payment_attempt_failed(
            attempt=attempt,
        )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.CANCELLED
    )


class FakeHostedPaymentProvider:
    def __init__(self) -> None:
        self.requests = []

    def create_payment(
        self,
        *,
        request,
    ) -> HostedPaymentSession:
        self.requests.append(
            request,
        )

        return HostedPaymentSession(
            provider_payment_id="provider-123",
            redirect_url="https://provider.example/pay",
        )


@pytest.mark.django_db
def test_create_hosted_payment_session_persists_provider_payment_id():
    order = _create_priced_order(
        amount=Decimal("12.50"),
    )

    attempt = create_payment_attempt(
        order=order,
    )

    provider = FakeHostedPaymentProvider()

    session = create_hosted_payment_session(
        attempt=attempt,
        provider=provider,
        customer_return_url=(
            "https://shop.example.com/return"
        ),
        webhook_url=(
            "https://shop.example.com/webhook"
        ),
    )

    attempt.refresh_from_db()

    assert (
        attempt.provider_payment_id
        == "provider-123"
    )
    assert (
        session.redirect_url
        == "https://provider.example/pay"
    )

    assert len(provider.requests) == 1

    request = provider.requests[0]

    assert request.reference == f"payment-{attempt.pk}"
    assert request.amount == Decimal("12.50")
    assert request.currency == Order.Currency.EUR


@pytest.mark.django_db
def test_hosted_payment_session_cannot_be_created_twice():
    order = _create_priced_order()

    attempt = create_payment_attempt(
        order=order,
    )

    provider = FakeHostedPaymentProvider()

    create_hosted_payment_session(
        attempt=attempt,
        provider=provider,
        customer_return_url="https://example.com/return",
        webhook_url="https://example.com/webhook",
    )

    with pytest.raises(
        InvalidPaymentAttempt,
        match="already has a provider payment",
    ):
        create_hosted_payment_session(
            attempt=attempt,
            provider=provider,
            customer_return_url="https://example.com/return",
            webhook_url="https://example.com/webhook",
        )

    assert len(provider.requests) == 1
