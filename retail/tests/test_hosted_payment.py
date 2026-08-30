from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.services import create_batch
from orders.models import Allocation
from payments.contracts import (
    HostedPaymentRequest,
    HostedPaymentSession,
)
from payments.models import PaymentAttempt
from payments.providers.sumup import SumUpPaymentError
from retail.payments import (
    begin_retail_hosted_payment,
    retry_retail_hosted_payment,
)
from retail.services import (
    AnonymousBuyerInput,
    InvalidRetailOrder,
    RetailOrderLineInput,
    create_pending_retail_order,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_offer_factory,
)


class FakeHostedPaymentProvider:
    def __init__(self) -> None:
        self.requests: list[HostedPaymentRequest] = []

    def create_payment(
        self,
        *,
        request: HostedPaymentRequest,
    ) -> HostedPaymentSession:
        self.requests.append(
            request
        )

        return HostedPaymentSession(
            provider_payment_id="sumup-checkout-123",
            redirect_url="https://checkout.sumup.test/pay/123",
        )


class FailingHostedPaymentProvider:
    def __init__(self) -> None:
        self.requests: list[HostedPaymentRequest] = []

    def create_payment(
        self,
        *,
        request: HostedPaymentRequest,
    ) -> HostedPaymentSession:
        self.requests.append(
            request
        )

        raise SumUpPaymentError(
            "Could not reach SumUp"
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
def test_begin_retail_hosted_payment_creates_provider_session(
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeHostedPaymentProvider()

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    result = begin_retail_hosted_payment(
        checkout=checkout,
        customer_return_url=(
            "https://shop.example.com/payment/return"
        ),
        webhook_url=(
            "https://shop.example.com/payment/webhook"
        ),
    )

    result.attempt.refresh_from_db()

    assert result.redirect_url == (
        "https://checkout.sumup.test/pay/123"
    )

    assert (
        result.attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        result.attempt.provider_payment_id
        == "sumup-checkout-123"
    )

    assert len(provider.requests) == 1

    request = provider.requests[0]

    assert request.amount == Decimal("25.00")
    assert request.currency == "EUR"
    assert (
        request.customer_return_url
        == "https://shop.example.com/payment/return"
    )
    assert (
        request.webhook_url
        == "https://shop.example.com/payment/webhook"
    )


@pytest.mark.django_db
def test_provider_failure_leaves_retryable_pending_attempt(
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FailingHostedPaymentProvider()

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    with pytest.raises(
        SumUpPaymentError,
        match="Could not reach SumUp",
    ):
        begin_retail_hosted_payment(
            checkout=checkout,
            customer_return_url=(
                "https://shop.example.com/payment/return"
            ),
            webhook_url=(
                "https://shop.example.com/payment/webhook"
            ),
        )

    attempt = PaymentAttempt.objects.get(
        order=checkout.order,
    )

    allocation = checkout.order.allocations.get()

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert attempt.provider_payment_id == ""

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is not None
    assert (
        allocation.reserved_until
        > timezone.now()
    )

    assert len(provider.requests) == 1


@pytest.mark.django_db
def test_retry_retail_hosted_payment_reuses_existing_attempt_and_reservation(
    monkeypatch,
):
    checkout = _create_checkout()

    failing_provider = FailingHostedPaymentProvider()

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: failing_provider,
    )

    with pytest.raises(
        SumUpPaymentError,
        match="Could not reach SumUp",
    ):
        begin_retail_hosted_payment(
            checkout=checkout,
            customer_return_url=(
                "https://shop.example.com/payment/return"
            ),
            webhook_url=(
                "https://shop.example.com/payment/webhook"
            ),
        )

    attempt = PaymentAttempt.objects.get(
        order=checkout.order,
    )

    allocation = checkout.order.allocations.get()

    original_attempt_id = attempt.pk
    original_allocation_id = allocation.pk
    original_reserved_until = allocation.reserved_until

    successful_provider = FakeHostedPaymentProvider()

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: successful_provider,
    )

    result = retry_retail_hosted_payment(
        attempt=attempt,
        customer_return_url=(
            "https://shop.example.com/payment/return"
        ),
        webhook_url=(
            "https://shop.example.com/payment/webhook"
        ),
    )

    result.attempt.refresh_from_db()
    allocation.refresh_from_db()

    assert result.attempt.pk == original_attempt_id

    assert (
        PaymentAttempt.objects
        .filter(order=checkout.order)
        .count()
        == 1
    )

    assert (
        result.attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        result.attempt.provider_payment_id
        == "sumup-checkout-123"
    )

    assert allocation.pk == original_allocation_id
    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert (
        allocation.reserved_until
        == original_reserved_until
    )

    assert result.redirect_url == (
        "https://checkout.sumup.test/pay/123"
    )

    assert len(failing_provider.requests) == 1
    assert len(successful_provider.requests) == 1

    first_request = failing_provider.requests[0]
    second_request = successful_provider.requests[0]

    assert (
        second_request.reference
        == first_request.reference
    )
    assert (
        second_request.amount
        == first_request.amount
    )
    assert (
        second_request.currency
        == first_request.currency
    )


@pytest.mark.django_db
def test_existing_provider_checkout_blocks_new_payment_start(
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeHostedPaymentProvider()

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    first_result = begin_retail_hosted_payment(
        checkout=checkout,
        customer_return_url=(
            "https://shop.example.com/payment/return"
        ),
        webhook_url=(
            "https://shop.example.com/payment/webhook"
        ),
    )

    allocation = checkout.order.allocations.get()
    original_reserved_until = allocation.reserved_until

    with pytest.raises(
        InvalidRetailOrder,
        match="already has a pending payment attempt",
    ):
        begin_retail_hosted_payment(
            checkout=checkout,
            customer_return_url=(
                "https://shop.example.com/payment/return"
            ),
            webhook_url=(
                "https://shop.example.com/payment/webhook"
            ),
        )

    first_result.attempt.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        first_result.attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        first_result.attempt.provider_payment_id
        == "sumup-checkout-123"
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

    assert len(provider.requests) == 1
