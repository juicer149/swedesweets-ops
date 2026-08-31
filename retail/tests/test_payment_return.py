from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from orders.models import Order
from payments.models import PaymentAttempt
from retail.models import RetailCheckoutSession
from retail.payments import (
    RetailPaymentRecovery,
    RetailPaymentRecoveryAction,
)
from retail.rules import RETAIL_CHECKOUT_WINDOW


@pytest.fixture
def payment_return_attempt():
    from django.utils import timezone

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        currency=Order.Currency.EUR,
        status=Order.Status.DRAFT,
    )

    checkout = RetailCheckoutSession.objects.create(
        order=order,
        expires_at=(
            timezone.now()
            + RETAIL_CHECKOUT_WINDOW
        ),
    )

    attempt = PaymentAttempt.objects.create(
        order=order,
        status=PaymentAttempt.Status.PENDING,
        provider=PaymentAttempt.Provider.SUMUP,
        provider_payment_id="sumup-return-test",
        amount=Decimal("25.00"),
        currency="EUR",
    )

    return checkout, attempt


@pytest.mark.django_db
def test_payment_return_is_public_and_shows_confirmation(
    client,
    monkeypatch,
    payment_return_attempt,
):
    checkout, attempt = payment_return_attempt

    def fake_recover_retail_payment(
        *,
        attempt: PaymentAttempt,
    ) -> RetailPaymentRecovery:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.CONFIRMED,
        )

    monkeypatch.setattr(
        "retail.views.recover_retail_payment",
        fake_recover_retail_payment,
    )

    response = client.get(
        reverse(
            "retail:payment_return",
            kwargs={
                "checkout_id": checkout.pk,
            },
        )
    )

    assert response.status_code == 200
    assert response.content == b"Payment confirmed."


@pytest.mark.django_db
def test_payment_return_redirects_to_existing_hosted_checkout(
    client,
    monkeypatch,
    payment_return_attempt,
):
    checkout, attempt = payment_return_attempt

    def fake_recover_retail_payment(
        *,
        attempt: PaymentAttempt,
    ) -> RetailPaymentRecovery:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.CONTINUE_PAYMENT,
            redirect_url="https://checkout.sumup.test/resume",
        )

    monkeypatch.setattr(
        "retail.views.recover_retail_payment",
        fake_recover_retail_payment,
    )

    response = client.get(
        reverse(
            "retail:payment_return",
            kwargs={
                "checkout_id": checkout.pk,
            },
        )
    )

    assert response.status_code == 302
    assert response.url == (
        "https://checkout.sumup.test/resume"
    )


@pytest.mark.django_db
def test_payment_return_shows_failed_state(
    client,
    monkeypatch,
    payment_return_attempt,
):
    checkout, attempt = payment_return_attempt

    def fake_recover_retail_payment(
        *,
        attempt: PaymentAttempt,
    ) -> RetailPaymentRecovery:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.PAYMENT_FAILED,
        )

    monkeypatch.setattr(
        "retail.views.recover_retail_payment",
        fake_recover_retail_payment,
    )

    response = client.get(
        reverse(
            "retail:payment_return",
            kwargs={
                "checkout_id": checkout.pk,
            },
        )
    )

    assert response.status_code == 200
    assert response.content == b"Payment failed."


@pytest.mark.django_db
def test_payment_return_shows_support_state(
    client,
    monkeypatch,
    payment_return_attempt,
):
    checkout, attempt = payment_return_attempt

    def fake_recover_retail_payment(
        *,
        attempt: PaymentAttempt,
    ) -> RetailPaymentRecovery:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.NEEDS_SUPPORT,
        )

    monkeypatch.setattr(
        "retail.views.recover_retail_payment",
        fake_recover_retail_payment,
    )

    response = client.get(
        reverse(
            "retail:payment_return",
            kwargs={
                "checkout_id": checkout.pk,
            },
        )
    )

    assert response.status_code == 200
    assert response.content == b"Payment requires support."


@pytest.mark.django_db
def test_payment_return_returns_not_found_for_unknown_checkout(
    client,
):
    import uuid

    response = client.get(
        reverse(
            "retail:payment_return",
            kwargs={
                "checkout_id": uuid.uuid4(),
            },
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_payment_return_returns_not_found_when_checkout_has_no_payment_attempt(
    client,
):
    from django.utils import timezone

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        currency=Order.Currency.EUR,
        status=Order.Status.DRAFT,
    )

    checkout = RetailCheckoutSession.objects.create(
        order=order,
        expires_at=(
            timezone.now()
            + RETAIL_CHECKOUT_WINDOW
        ),
    )

    response = client.get(
        reverse(
            "retail:payment_return",
            kwargs={
                "checkout_id": checkout.pk,
            },
        )
    )

    assert response.status_code == 404
