from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from inventory.services import create_batch
from orders.models import (
    Allocation,
    Order,
)
from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
)
from payments.models import PaymentAttempt
from payments.providers.sumup import SumUpPaymentError
from retail.reconciliation import (
    PaymentReconciliationSummary,
    reconcile_pending_retail_payments,
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
    retail_product_factory,
    retail_product_offer_factory,
)


class FakeReconciliationProvider:
    def __init__(
        self,
        *,
        results: dict[
            str,
            ExternalPaymentState | Exception,
        ],
    ) -> None:
        self.results = results
        self.requested_payment_ids: list[str] = []

    def get_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> ExternalPaymentState:
        self.requested_payment_ids.append(
            provider_payment_id
        )

        result = self.results[
            provider_payment_id
        ]

        if isinstance(
            result,
            Exception,
        ):
            raise result

        return result


def _create_pending_attempt(
    *,
    suffix: str,
    provider_payment_id: str = "",
) -> tuple[
    Order,
    PaymentAttempt,
    Allocation,
]:
    product = retail_product_factory(
        name=f"Product {suffix}",
    )

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id=f"BATCH-{suffix}",
        product=product,
        quantity=10,
        best_before=(
            timezone.localdate()
            + timedelta(days=60)
        ),
        location=f"Shelf {suffix}",
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

    if provider_payment_id:
        attempt.provider_payment_id = provider_payment_id
        attempt.save(
            update_fields=[
                "provider_payment_id",
                "updated_at",
            ]
        )

    allocation = checkout.order.allocations.get()

    return (
        checkout.order,
        attempt,
        allocation,
    )


@pytest.mark.django_db
def test_batch_reconciliation_isolates_provider_errors_and_continues(
    monkeypatch,
):
    retail_postal_area_factory()

    (
        successful_order,
        successful_attempt,
        successful_allocation,
    ) = _create_pending_attempt(
        suffix="SUCCESS",
        provider_payment_id="checkout-success",
    )

    (
        errored_order,
        errored_attempt,
        errored_allocation,
    ) = _create_pending_attempt(
        suffix="ERROR",
        provider_payment_id="checkout-error",
    )

    (
        failed_order,
        failed_attempt,
        failed_allocation,
    ) = _create_pending_attempt(
        suffix="FAILED",
        provider_payment_id="checkout-failed",
    )

    (
        unresolved_order,
        unresolved_attempt,
        unresolved_allocation,
    ) = _create_pending_attempt(
        suffix="UNRESOLVED",
    )

    provider = FakeReconciliationProvider(
        results={
            "checkout-success": ExternalPaymentState(
                provider_payment_id="checkout-success",
                status=ExternalPaymentStatus.SUCCEEDED,
                provider_transaction_id="transaction-success",
            ),
            "checkout-error": SumUpPaymentError(
                "SumUp temporarily unavailable"
            ),
            "checkout-failed": ExternalPaymentState(
                provider_payment_id="checkout-failed",
                status=ExternalPaymentStatus.FAILED,
            ),
        }
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    summary = reconcile_pending_retail_payments()

    successful_order.refresh_from_db()
    successful_attempt.refresh_from_db()
    successful_allocation.refresh_from_db()

    errored_order.refresh_from_db()
    errored_attempt.refresh_from_db()
    errored_allocation.refresh_from_db()

    failed_order.refresh_from_db()
    failed_attempt.refresh_from_db()
    failed_allocation.refresh_from_db()

    unresolved_order.refresh_from_db()
    unresolved_attempt.refresh_from_db()
    unresolved_allocation.refresh_from_db()

    assert summary == PaymentReconciliationSummary(
        selected=4,
        checked=3,
        succeeded=1,
        failed=1,
        pending=0,
        cancelled=0,
        unresolved=1,
        errors=1,
    )

    assert provider.requested_payment_ids == [
        "checkout-success",
        "checkout-error",
        "checkout-failed",
    ]

    assert (
        successful_attempt.status
        == PaymentAttempt.Status.SUCCEEDED
    )
    assert (
        successful_attempt.provider_transaction_id
        == "transaction-success"
    )
    assert (
        successful_order.status
        == Order.Status.PLACED
    )
    assert (
        successful_allocation.status
        == Allocation.Status.RESERVED
    )
    assert successful_allocation.reserved_until is None

    assert (
        errored_attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert (
        errored_order.status
        == Order.Status.DRAFT
    )
    assert (
        errored_allocation.status
        == Allocation.Status.RESERVED
    )
    assert errored_allocation.reserved_until is not None

    assert (
        failed_attempt.status
        == PaymentAttempt.Status.FAILED
    )
    assert (
        failed_order.status
        == Order.Status.DRAFT
    )
    assert (
        failed_allocation.status
        == Allocation.Status.CANCELLED
    )

    assert (
        unresolved_attempt.status
        == PaymentAttempt.Status.PENDING
    )
    assert unresolved_attempt.provider_payment_id == ""
    assert (
        unresolved_order.status
        == Order.Status.DRAFT
    )
    assert (
        unresolved_allocation.status
        == Allocation.Status.RESERVED
    )
    assert unresolved_allocation.reserved_until is not None


@pytest.mark.django_db
def test_batch_reconciliation_counts_provider_pending_payment(
    monkeypatch,
):
    retail_postal_area_factory()

    order, attempt, allocation = (
        _create_pending_attempt(
            suffix="PENDING",
            provider_payment_id="checkout-pending",
        )
    )

    provider = FakeReconciliationProvider(
        results={
            "checkout-pending": ExternalPaymentState(
                provider_payment_id="checkout-pending",
                status=ExternalPaymentStatus.PENDING,
            ),
        }
    )

    monkeypatch.setattr(
        "retail.payments.get_default_hosted_payment_provider",
        lambda: provider,
    )

    summary = reconcile_pending_retail_payments()

    order.refresh_from_db()
    attempt.refresh_from_db()
    allocation.refresh_from_db()

    assert summary == PaymentReconciliationSummary(
        selected=1,
        checked=1,
        succeeded=0,
        failed=0,
        pending=1,
        cancelled=0,
        unresolved=0,
        errors=0,
    )

    assert (
        provider.requested_payment_ids
        == [
            "checkout-pending",
        ]
    )

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
    assert allocation.reserved_until is not None


def test_reconcile_payments_management_command_reports_summary(
    monkeypatch,
):
    summary = PaymentReconciliationSummary(
        selected=4,
        checked=3,
        succeeded=1,
        failed=1,
        pending=0,
        cancelled=0,
        unresolved=1,
        errors=0,
    )

    monkeypatch.setattr(
        "config.management.commands.reconcile_payments."
        "reconcile_pending_retail_payments",
        lambda: summary,
    )

    stdout = StringIO()

    call_command(
        "reconcile_payments",
        stdout=stdout,
    )

    output = stdout.getvalue()

    assert "Payment reconciliation complete:" in output
    assert "selected=4" in output
    assert "checked=3" in output
    assert "succeeded=1" in output
    assert "failed=1" in output
    assert "pending=0" in output
    assert "cancelled=0" in output
    assert "unresolved=1" in output
    assert "errors=0" in output
