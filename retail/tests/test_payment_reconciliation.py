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
from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
    HostedPaymentSession,
)
from payments.models import PaymentAttempt
from retail.payments import (
    PaymentReconciliationConflict,
    begin_retail_hosted_payment,
    reconcile_retail_payment,
)
from retail.services import (
    AnonymousBuyerInput,
    RetailOrderLineInput,
    create_pending_retail_order,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_price_factory,
)


class FakePaymentProvider:
    def __init__(
        self,
        *,
        state: ExternalPaymentState,
    ) -> None:
        self.state = state

    def create_payment(
        self,
        *,
        request,
    ) -> HostedPaymentSession:
        return HostedPaymentSession(
            provider_payment_id=self.state.provider_payment_id,
            redirect_url="https://checkout.example/pay",
        )

    def get_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> ExternalPaymentState:
        assert (
            provider_payment_id
            == self.state.provider_payment_id
        )

        return self.state


def _create_attempt(
    monkeypatch,
) -> tuple[
    Order,
    PaymentAttempt,
    Allocation,
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

    creation_provider = FakePaymentProvider(
        state=ExternalPaymentState(
            provider_payment_id="sumup-checkout-123",
            status=ExternalPaymentStatus.PENDING,
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: creation_provider,
    )

    result = begin_retail_hosted_payment(
        checkout=checkout,
        customer_return_url="https://shop.example/return",
        webhook_url="https://shop.example/webhook",
    )

    allocation = result.attempt.order.allocations.get()

    return (
        result.attempt.order,
        result.attempt,
        allocation,
    )


@pytest.mark.django_db
def test_pending_provider_payment_leaves_local_state_unchanged(
    monkeypatch,
):
    order, attempt, allocation = _create_attempt(
        monkeypatch,
    )

    provider = FakePaymentProvider(
        state=ExternalPaymentState(
            provider_payment_id="sumup-checkout-123",
            status=ExternalPaymentStatus.PENDING,
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    reconciled = reconcile_retail_payment(
        attempt=attempt,
    )

    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        reconciled.status
        == PaymentAttempt.Status.PENDING
    )
    assert order.status == Order.Status.DRAFT
    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is not None


@pytest.mark.django_db
def test_successful_provider_payment_places_order(
    monkeypatch,
):
    order, attempt, allocation = _create_attempt(
        monkeypatch,
    )

    provider = FakePaymentProvider(
        state=ExternalPaymentState(
            provider_payment_id="sumup-checkout-123",
            status=ExternalPaymentStatus.SUCCEEDED,
            provider_transaction_id="transaction-456",
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    reconciled = reconcile_retail_payment(
        attempt=attempt,
    )

    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        reconciled.status
        == PaymentAttempt.Status.SUCCEEDED
    )
    assert (
        reconciled.provider_transaction_id
        == "transaction-456"
    )
    assert order.status == Order.Status.PLACED
    assert (
        allocation.status
        == Allocation.Status.RESERVED
    )
    assert allocation.reserved_until is None


@pytest.mark.django_db
def test_failed_provider_payment_releases_reservation(
    monkeypatch,
):
    order, attempt, allocation = _create_attempt(
        monkeypatch,
    )

    provider = FakePaymentProvider(
        state=ExternalPaymentState(
            provider_payment_id="sumup-checkout-123",
            status=ExternalPaymentStatus.FAILED,
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    reconciled = reconcile_retail_payment(
        attempt=attempt,
    )

    order.refresh_from_db()
    allocation.refresh_from_db()

    assert (
        reconciled.status
        == PaymentAttempt.Status.FAILED
    )
    assert order.status == Order.Status.DRAFT
    assert (
        allocation.status
        == Allocation.Status.CANCELLED
    )


@pytest.mark.django_db
def test_success_reconciliation_is_idempotent(
    monkeypatch,
):
    order, attempt, _allocation = _create_attempt(
        monkeypatch,
    )

    provider = FakePaymentProvider(
        state=ExternalPaymentState(
            provider_payment_id="sumup-checkout-123",
            status=ExternalPaymentStatus.SUCCEEDED,
            provider_transaction_id="transaction-456",
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    first = reconcile_retail_payment(
        attempt=attempt,
    )

    second = reconcile_retail_payment(
        attempt=first,
    )

    order.refresh_from_db()

    assert (
        second.status
        == PaymentAttempt.Status.SUCCEEDED
    )
    assert order.status == Order.Status.PLACED
    assert (
        second.provider_transaction_id
        == "transaction-456"
    )


@pytest.mark.django_db
def test_paid_provider_state_conflicts_with_cancelled_local_attempt(
    monkeypatch,
):
    _order, attempt, _allocation = _create_attempt(
        monkeypatch,
    )

    attempt.status = PaymentAttempt.Status.CANCELLED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    provider = FakePaymentProvider(
        state=ExternalPaymentState(
            provider_payment_id="sumup-checkout-123",
            status=ExternalPaymentStatus.SUCCEEDED,
            provider_transaction_id="transaction-456",
        )
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    with pytest.raises(
        PaymentReconciliationConflict,
        match="successful payment",
    ):
        reconcile_retail_payment(
            attempt=attempt,
        )
