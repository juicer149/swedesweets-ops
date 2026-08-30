from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.services import create_batch
from payments.contracts import HostedPaymentSession
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


class FakeHostedPaymentProvider:
    def __init__(self) -> None:
        self.requests = []

    def create_payment(
        self,
        *,
        request,
    ) -> HostedPaymentSession:
        self.requests.append(request)

        return HostedPaymentSession(
            provider_payment_id="sumup-checkout-123",
            redirect_url="https://checkout.sumup.test/pay/123",
        )


@pytest.mark.django_db
def test_begin_retail_hosted_payment_creates_provider_session(
    monkeypatch,
):
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
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
