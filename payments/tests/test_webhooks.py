from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.urls import reverse

from orders.models import Order
from payments.models import PaymentAttempt
from retail.payments import (
    PaymentReconciliationConflict,
)


@pytest.fixture
def payment_attempt():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        currency=Order.Currency.EUR,
        status=Order.Status.DRAFT,
    )

    return PaymentAttempt.objects.create(
        order=order,
        status=PaymentAttempt.Status.PENDING,
        provider=PaymentAttempt.Provider.SUMUP,
        provider_payment_id="sumup-checkout-123",
        amount=Decimal("25.00"),
        currency="EUR",
    )


@pytest.mark.django_db
def test_sumup_webhook_is_public_and_reconciles_known_checkout(
    client,
    monkeypatch,
    payment_attempt,
):
    reconciled_attempts = []

    def fake_reconcile_retail_payment(
        *,
        attempt,
    ):
        reconciled_attempts.append(
            attempt
        )

        return attempt

    monkeypatch.setattr(
        "payments.views.reconcile_retail_payment",
        fake_reconcile_retail_payment,
    )

    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": (
                    "CHECKOUT_STATUS_CHANGED"
                ),
                "id": "sumup-checkout-123",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 204

    assert len(reconciled_attempts) == 1
    assert (
        reconciled_attempts[0].pk
        == payment_attempt.pk
    )


@pytest.mark.django_db
def test_sumup_webhook_rejects_invalid_json(
    client,
):
    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data="{not-json",
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_sumup_webhook_rejects_non_object_json(
    client,
):
    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            [
                "CHECKOUT_STATUS_CHANGED",
            ]
        ),
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_sumup_webhook_ignores_unknown_event_type(
    client,
    monkeypatch,
):
    def unexpected_reconciliation(
        *,
        attempt,
    ):
        raise AssertionError(
            "unknown events must not be reconciled"
        )

    monkeypatch.setattr(
        "payments.views.reconcile_retail_payment",
        unexpected_reconciliation,
    )

    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": "SOMETHING_NEW",
                "id": "sumup-checkout-123",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_sumup_webhook_requires_checkout_id_for_known_event(
    client,
):
    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": (
                    "CHECKOUT_STATUS_CHANGED"
                ),
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_sumup_webhook_ignores_unknown_checkout(
    client,
    monkeypatch,
):
    def unexpected_reconciliation(
        *,
        attempt,
    ):
        raise AssertionError(
            "unknown checkout must not be reconciled"
        )

    monkeypatch.setattr(
        "payments.views.reconcile_retail_payment",
        unexpected_reconciliation,
    )

    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": (
                    "CHECKOUT_STATUS_CHANGED"
                ),
                "id": "unknown-checkout",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_sumup_webhook_returns_server_error_on_reconciliation_conflict(
    client,
    monkeypatch,
    payment_attempt,
):
    def conflicting_reconciliation(
        *,
        attempt,
    ):
        raise PaymentReconciliationConflict(
            "provider and local state conflict"
        )

    monkeypatch.setattr(
        "payments.views.reconcile_retail_payment",
        conflicting_reconciliation,
    )

    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": (
                    "CHECKOUT_STATUS_CHANGED"
                ),
                "id": "sumup-checkout-123",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 500


@pytest.mark.django_db
def test_sumup_webhook_rejects_get(
    client,
):
    response = client.get(
        reverse(
            "payments:sumup_webhook"
        ),
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_sumup_webhook_returns_server_error_when_reconciliation_fails(
    client,
    monkeypatch,
    payment_attempt,
):
    def failed_reconciliation(
        *,
        attempt,
    ):
        raise RuntimeError(
            "reconciliation failed"
        )

    monkeypatch.setattr(
        "payments.views.reconcile_retail_payment",
        failed_reconciliation,
    )

    response = client.post(
        reverse(
            "payments:sumup_webhook"
        ),
        data=json.dumps(
            {
                "event_type": (
                    "CHECKOUT_STATUS_CHANGED"
                ),
                "id": "sumup-checkout-123",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 500
