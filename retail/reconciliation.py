from __future__ import annotations

from dataclasses import dataclass
import logging

from orders.models import Order
from payments.models import PaymentAttempt
from payments.selectors import (
    list_pending_payment_attempt_ids,
)
from retail.payments import (
    reconcile_retail_payment,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PaymentReconciliationSummary:
    selected: int
    checked: int
    succeeded: int
    failed: int
    pending: int
    cancelled: int
    unresolved: int
    errors: int


def reconcile_pending_retail_payments() -> PaymentReconciliationSummary:
    """Reconcile pending SumUp-backed retail payments independently.

    Each payment attempt is processed as its own unit of work.

    Provider failures or reconciliation conflicts for one attempt do not stop
    reconciliation of later attempts.

    Pending attempts without a provider payment id are intentionally left
    untouched because their external creation state cannot yet be determined
    from the provider id.
    """

    attempt_ids = list_pending_payment_attempt_ids(
        provider=PaymentAttempt.Provider.SUMUP,
        order_channel=Order.Channel.RETAIL,
    )

    checked = 0
    succeeded = 0
    failed = 0
    pending = 0
    cancelled = 0
    unresolved = 0
    errors = 0

    for attempt_id in attempt_ids:
        try:
            attempt = PaymentAttempt.objects.get(
                pk=attempt_id,
            )
        except PaymentAttempt.DoesNotExist:
            errors += 1

            logger.warning(
                "Payment attempt %s disappeared before reconciliation.",
                attempt_id,
            )

            continue

        # Another worker or webhook may have reconciled the attempt after the
        # initial id snapshot was taken.
        if attempt.status != PaymentAttempt.Status.PENDING:
            continue

        if not attempt.provider_payment_id:
            unresolved += 1

            logger.info(
                "Payment attempt %s is pending without a provider payment id.",
                attempt.pk,
            )

            continue

        checked += 1

        try:
            reconciled = reconcile_retail_payment(
                attempt=attempt,
            )
        except Exception:
            errors += 1

            logger.exception(
                "Could not reconcile payment attempt %s.",
                attempt.pk,
            )

            continue

        if reconciled.status == PaymentAttempt.Status.SUCCEEDED:
            succeeded += 1
            continue

        if reconciled.status == PaymentAttempt.Status.FAILED:
            failed += 1
            continue

        if reconciled.status == PaymentAttempt.Status.PENDING:
            pending += 1
            continue

        if reconciled.status == PaymentAttempt.Status.CANCELLED:
            cancelled += 1
            continue

        errors += 1

        logger.error(
            "Payment attempt %s returned unsupported local status %s.",
            reconciled.pk,
            reconciled.status,
        )

    return PaymentReconciliationSummary(
        selected=len(attempt_ids),
        checked=checked,
        succeeded=succeeded,
        failed=failed,
        pending=pending,
        cancelled=cancelled,
        unresolved=unresolved,
        errors=errors,
    )
