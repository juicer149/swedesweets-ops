from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.services import create_batch
from orders.models import Order
from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
)
from payments.models import PaymentAttempt
from payments.providers.sumup import SumUpPaymentError
from retail.payments import (
    RetailPaymentRecoveryAction,
    recover_retail_payment,
)
from retail.services import (
    AnonymousBuyerInput,
    RetailOrderLineInput,
    create_pending_retail_order,
    start_retail_payment,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_price_factory,
)


class FakeRecoveryProvider:
    def __init__(
        self,
        *,
        state: ExternalPaymentState | None = None,
        error: Exception | None = None,
    ) -> None:
        self.state = state
        self.error = error
        self.requested_payment_ids: list[str] = []

    def get_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> ExternalPaymentState:
        self.requested_payment_ids.append(
            provider_payment_id
        )

        if self.error is not None:
            raise self.error

        assert self.state is not None

        return self.state


def _create_attempt(
    *,
    provider_payment_id: str = "",
) -> tuple[
    Order,
    PaymentAttempt,
]:
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    attempt = start_retail_payment(
        checkout=checkout,
    )

    if provider_payment_id:
        attempt.provider_payment_id = provider_payment_id
        attempt.save(
            update_fields=[
                "provider_payment_id",
                "updated_at",
            ]
        )

    return (
        checkout.order,
        attempt,
    )


@pytest.mark.django_db
def test_recovery_routes_pending_checkout_back_to_existing_provider_session(
    monkeypatch,
):
    order, attempt = _create_attempt(
        provider_payment_id="checkout-123",
    )

    provider = FakeRecoveryProvider(
        state=ExternalPaymentState(
            provider_payment_id="checkout-123",
            status=ExternalPaymentStatus.PENDING,
            hosted_payment_url=(
                "https://checkout.sumup.com/pay/123"
            ),
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    order.refresh_from_db()
    attempt.refresh_from_db()

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.CONTINUE_PAYMENT
    )
    assert (
        recovery.redirect_url
        == "https://checkout.sumup.com/pay/123"
    )

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert order.status == Order.Status.DRAFT

    assert provider.requested_payment_ids == [
        "checkout-123",
    ]


@pytest.mark.django_db
def test_recovery_confirms_provider_success(
    monkeypatch,
):
    order, attempt = _create_attempt(
        provider_payment_id="checkout-123",
    )

    provider = FakeRecoveryProvider(
        state=ExternalPaymentState(
            provider_payment_id="checkout-123",
            status=ExternalPaymentStatus.SUCCEEDED,
            provider_transaction_id="transaction-456",
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    order.refresh_from_db()
    attempt.refresh_from_db()

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.CONFIRMED
    )

    assert (
        attempt.status
        == PaymentAttempt.Status.SUCCEEDED
    )
    assert (
        attempt.provider_transaction_id
        == "transaction-456"
    )
    assert order.status == Order.Status.PLACED


@pytest.mark.django_db
def test_recovery_reports_provider_failure(
    monkeypatch,
):
    order, attempt = _create_attempt(
        provider_payment_id="checkout-123",
    )

    provider = FakeRecoveryProvider(
        state=ExternalPaymentState(
            provider_payment_id="checkout-123",
            status=ExternalPaymentStatus.FAILED,
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    order.refresh_from_db()
    attempt.refresh_from_db()

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.PAYMENT_FAILED
    )

    assert (
        attempt.status
        == PaymentAttempt.Status.FAILED
    )
    assert order.status == Order.Status.DRAFT


@pytest.mark.django_db
def test_recovery_confirms_already_succeeded_local_payment(
    monkeypatch,
):
    order, attempt = _create_attempt()

    attempt.status = PaymentAttempt.Status.SUCCEEDED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    def unexpected_provider():
        raise AssertionError(
            "already succeeded local payment must not call provider"
        )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        unexpected_provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.CONFIRMED
    )


@pytest.mark.django_db
def test_recovery_reports_already_failed_local_payment(
    monkeypatch,
):
    _order, attempt = _create_attempt()

    attempt.status = PaymentAttempt.Status.FAILED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    def unexpected_provider():
        raise AssertionError(
            "already failed local payment must not call provider"
        )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        unexpected_provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.PAYMENT_FAILED
    )


@pytest.mark.django_db
def test_recovery_requires_support_when_provider_initialization_is_unknown():
    _order, attempt = _create_attempt()

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert attempt.provider_payment_id == ""

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.NEEDS_SUPPORT
    )
    assert recovery.redirect_url is None


@pytest.mark.django_db
def test_recovery_requires_support_when_provider_is_unavailable(
    monkeypatch,
):
    _order, attempt = _create_attempt(
        provider_payment_id="checkout-123",
    )

    provider = FakeRecoveryProvider(
        error=SumUpPaymentError(
            "Could not reach SumUp"
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.NEEDS_SUPPORT
    )


@pytest.mark.django_db
def test_recovery_requires_support_when_pending_checkout_has_no_hosted_url(
    monkeypatch,
):
    _order, attempt = _create_attempt(
        provider_payment_id="checkout-123",
    )

    provider = FakeRecoveryProvider(
        state=ExternalPaymentState(
            provider_payment_id="checkout-123",
            status=ExternalPaymentStatus.PENDING,
            hosted_payment_url=None,
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.NEEDS_SUPPORT
    )
    assert recovery.redirect_url is None


@pytest.mark.django_db
def test_recovery_requires_support_for_provider_local_conflict(
    monkeypatch,
):
    _order, attempt = _create_attempt(
        provider_payment_id="checkout-123",
    )

    attempt.status = PaymentAttempt.Status.CANCELLED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    provider = FakeRecoveryProvider(
        state=ExternalPaymentState(
            provider_payment_id="checkout-123",
            status=ExternalPaymentStatus.SUCCEEDED,
            provider_transaction_id="transaction-456",
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    attempt.refresh_from_db()

    assert (
        attempt.status
        == PaymentAttempt.Status.CANCELLED
    )

    assert (
        recovery.action
        == RetailPaymentRecoveryAction.NEEDS_SUPPORT
    )
