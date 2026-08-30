from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from inventory.services import create_batch
from orders.models import (
    Allocation,
    Order,
)
from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
    HostedPaymentRequest,
    HostedPaymentSession,
)
from payments.models import PaymentAttempt
from retail.payments import begin_retail_hosted_payment
from retail.services import (
    AnonymousBuyerInput,
    RetailOrderLineInput,
    create_pending_retail_order,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_offer_factory,
)


class FakeSumUpProvider:
    def __init__(self) -> None:
        self.state = ExternalPaymentState(
            provider_payment_id="checkout-integration-123",
            status=ExternalPaymentStatus.PENDING,
            hosted_payment_url=(
                "https://checkout.sumup.test/pay/integration-123"
            ),
        )
        self.create_requests: list[HostedPaymentRequest] = []
        self.get_requests: list[str] = []

    def create_payment(
        self,
        *,
        request: HostedPaymentRequest,
    ) -> HostedPaymentSession:
        self.create_requests.append(
            request
        )

        return HostedPaymentSession(
            provider_payment_id=(
                self.state.provider_payment_id
            ),
            redirect_url=(
                "https://checkout.sumup.test/pay/integration-123"
            ),
        )

    def get_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> ExternalPaymentState:
        self.get_requests.append(
            provider_payment_id
        )

        assert (
            provider_payment_id
            == self.state.provider_payment_id
        )

        return self.state


def _create_checkout():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="INTEGRATION-001",
        product=offer.product,
        quantity=10,
        best_before=(
            timezone.localdate()
            + timedelta(days=60)
        ),
        location="Integration Shelf",
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


def _post_sumup_webhook(
    *,
    client,
    provider_payment_id: str,
):
    return client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": (
                    "CHECKOUT_STATUS_CHANGED"
                ),
                "id": provider_payment_id,
            }
        ),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_retail_payment_happy_path_from_checkout_to_webhook_confirmation(
    client,
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeSumUpProvider()

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
            "https://shop.example.com/payments/sumup/webhook"
        ),
    )

    attempt = result.attempt
    order = checkout.order
    allocation = order.allocations.get()

    attempt.refresh_from_db()
    order.refresh_from_db()
    allocation.refresh_from_db()

    assert result.redirect_url == (
        "https://checkout.sumup.test/pay/integration-123"
    )

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        attempt.provider_payment_id
        == "checkout-integration-123"
    )

    assert (
        order.status
        == Order.Status.DRAFT
    )

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is not None

    assert len(provider.create_requests) == 1

    create_request = provider.create_requests[0]

    assert create_request.amount == Decimal("25.00")
    assert create_request.currency == "EUR"
    assert (
        create_request.reference
        == f"payment-{attempt.pk}"
    )

    provider.state = ExternalPaymentState(
        provider_payment_id="checkout-integration-123",
        status=ExternalPaymentStatus.SUCCEEDED,
        provider_transaction_id="transaction-integration-456",
    )

    response = _post_sumup_webhook(
        client=client,
        provider_payment_id="checkout-integration-123",
    )

    assert response.status_code == 204

    attempt.refresh_from_db()
    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.SUCCEEDED
    )
    assert (
        attempt.provider_transaction_id
        == "transaction-integration-456"
    )

    assert (
        order.status
        == Order.Status.PLACED
    )

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is None

    assert provider.get_requests == [
        "checkout-integration-123",
    ]


@pytest.mark.django_db
def test_retail_payment_failed_provider_state_releases_stock(
    client,
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeSumUpProvider()

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
            "https://shop.example.com/payments/sumup/webhook"
        ),
    )

    attempt = result.attempt
    order = checkout.order
    allocation = order.allocations.get()

    provider.state = ExternalPaymentState(
        provider_payment_id="checkout-integration-123",
        status=ExternalPaymentStatus.FAILED,
    )

    response = _post_sumup_webhook(
        client=client,
        provider_payment_id="checkout-integration-123",
    )

    assert response.status_code == 204

    attempt.refresh_from_db()
    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.FAILED
    )

    assert (
        order.status
        == Order.Status.DRAFT
    )

    assert (
        allocation.status
        == Allocation.Status.CANCELLED
    )


@pytest.mark.django_db
def test_retail_payment_pending_webhook_preserves_temporary_hold(
    client,
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeSumUpProvider()

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
            "https://shop.example.com/payments/sumup/webhook"
        ),
    )

    attempt = result.attempt
    order = checkout.order
    allocation = order.allocations.get()

    original_reserved_until = (
        allocation.reserved_until
    )

    response = _post_sumup_webhook(
        client=client,
        provider_payment_id="checkout-integration-123",
    )

    assert response.status_code == 204

    attempt.refresh_from_db()
    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        order.status
        == Order.Status.DRAFT
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
def test_successful_webhook_is_idempotent_across_full_payment_flow(
    client,
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeSumUpProvider()

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
            "https://shop.example.com/payments/sumup/webhook"
        ),
    )

    attempt = result.attempt
    order = checkout.order
    allocation = order.allocations.get()

    provider.state = ExternalPaymentState(
        provider_payment_id="checkout-integration-123",
        status=ExternalPaymentStatus.SUCCEEDED,
        provider_transaction_id="transaction-integration-456",
    )

    first_response = _post_sumup_webhook(
        client=client,
        provider_payment_id="checkout-integration-123",
    )

    second_response = _post_sumup_webhook(
        client=client,
        provider_payment_id="checkout-integration-123",
    )

    assert first_response.status_code == 204
    assert second_response.status_code == 204

    attempt.refresh_from_db()
    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.SUCCEEDED
    )
    assert (
        attempt.provider_transaction_id
        == "transaction-integration-456"
    )

    assert (
        order.status
        == Order.Status.PLACED
    )

    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is None

    assert (
        PaymentAttempt.objects
        .filter(order=order)
        .count()
        == 1
    )

    assert provider.get_requests == [
        "checkout-integration-123",
        "checkout-integration-123",
    ]


@pytest.mark.django_db
def test_paid_webhook_after_temporary_reservation_expiry_does_not_place_order(
    client,
    monkeypatch,
):
    checkout = _create_checkout()

    provider = FakeSumUpProvider()

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
            "https://shop.example.com/payments/sumup/webhook"
        ),
    )

    attempt = result.attempt
    order = checkout.order
    allocation = order.allocations.get()

    Allocation.objects.filter(
        pk=allocation.pk,
    ).update(
        reserved_until=(
            timezone.now()
            - timedelta(seconds=1)
        )
    )

    allocation.refresh_from_db()

    provider.state = ExternalPaymentState(
        provider_payment_id="checkout-integration-123",
        status=ExternalPaymentStatus.SUCCEEDED,
        provider_transaction_id="transaction-integration-expired",
    )

    client.raise_request_exception = False

    response = _post_sumup_webhook(
        client=client,
        provider_payment_id="checkout-integration-123",
    )

    assert response.status_code == 500

    attempt.refresh_from_db()
    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        order.status
        == Order.Status.DRAFT
    )
    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert (
        allocation.reserved_until
        <= timezone.now()
    )
