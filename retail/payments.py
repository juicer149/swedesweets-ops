from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
)
from payments.models import PaymentAttempt
from payments.providers.factory import (
    get_default_hosted_payment_provider,
)
from payments.services import (
    InvalidPaymentAttempt,
    create_hosted_payment_session,
)
from retail.models import RetailCheckoutSession
from retail.services import (
    complete_retail_payment,
    fail_retail_payment,
    start_retail_payment,
)


class PaymentReconciliationConflict(RuntimeError):
    """Provider truth conflicts with an irreversible local payment state."""


class RetailPaymentRecoveryAction(StrEnum):
    CONTINUE_PAYMENT = "continue_payment"
    CONFIRMED = "confirmed"
    PAYMENT_FAILED = "payment_failed"
    NEEDS_SUPPORT = "needs_support"


@dataclass(frozen=True, slots=True)
class RetailPaymentRedirect:
    attempt: PaymentAttempt
    redirect_url: str


@dataclass(frozen=True, slots=True)
class RetailPaymentRecovery:
    attempt: PaymentAttempt
    action: RetailPaymentRecoveryAction
    redirect_url: str | None = None


def begin_retail_hosted_payment(
    *,
    checkout: RetailCheckoutSession,
    customer_return_url: str,
    webhook_url: str,
) -> RetailPaymentRedirect:
    """Start a retail payment and create its external hosted checkout."""

    attempt = start_retail_payment(
        checkout=checkout,
    )

    return _create_retail_hosted_payment_session(
        attempt=attempt,
        customer_return_url=customer_return_url,
        webhook_url=webhook_url,
    )


def retry_retail_hosted_payment(
    *,
    attempt: PaymentAttempt,
    customer_return_url: str,
    webhook_url: str,
) -> RetailPaymentRedirect:
    """Retry provider initialization for the same local attempt."""

    return _create_retail_hosted_payment_session(
        attempt=attempt,
        customer_return_url=customer_return_url,
        webhook_url=webhook_url,
    )


def recover_retail_payment(
    *,
    attempt: PaymentAttempt,
) -> RetailPaymentRecovery:
    """Resolve the customer-facing state of one retail payment.

    Recovery never guesses about unknown external payment creation.

    A pending attempt without a provider payment id is therefore routed to
    support instead of implicitly creating another external checkout.
    """

    attempt = (
        PaymentAttempt.objects
        .select_related("order")
        .get(pk=attempt.pk)
    )

    if attempt.status == PaymentAttempt.Status.SUCCEEDED:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.CONFIRMED,
        )

    if attempt.status == PaymentAttempt.Status.FAILED:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.PAYMENT_FAILED,
        )

    if (
        attempt.status == PaymentAttempt.Status.CANCELLED
        and not attempt.provider_payment_id
    ):
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.PAYMENT_FAILED,
        )

    if not attempt.provider_payment_id:
        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.NEEDS_SUPPORT,
        )

    try:
        external = _get_external_payment_state(
            attempt=attempt,
        )

        reconciled = _reconcile_retail_payment_state(
            attempt=attempt,
            external=external,
        )
    except Exception:
        attempt.refresh_from_db()

        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.NEEDS_SUPPORT,
        )

    if reconciled.status == PaymentAttempt.Status.SUCCEEDED:
        return RetailPaymentRecovery(
            attempt=reconciled,
            action=RetailPaymentRecoveryAction.CONFIRMED,
        )

    if reconciled.status in {
        PaymentAttempt.Status.FAILED,
        PaymentAttempt.Status.CANCELLED,
    }:
        return RetailPaymentRecovery(
            attempt=reconciled,
            action=RetailPaymentRecoveryAction.PAYMENT_FAILED,
        )

    if reconciled.status != PaymentAttempt.Status.PENDING:
        return RetailPaymentRecovery(
            attempt=reconciled,
            action=RetailPaymentRecoveryAction.NEEDS_SUPPORT,
        )

    if not external.hosted_payment_url:
        return RetailPaymentRecovery(
            attempt=reconciled,
            action=RetailPaymentRecoveryAction.NEEDS_SUPPORT,
        )

    return RetailPaymentRecovery(
        attempt=reconciled,
        action=RetailPaymentRecoveryAction.CONTINUE_PAYMENT,
        redirect_url=external.hosted_payment_url,
    )


def reconcile_retail_payment(
    *,
    attempt: PaymentAttempt,
) -> PaymentAttempt:
    """Reconcile local state against provider-authoritative state.

    Provider I/O happens before any local transition transaction begins.

    Repeated terminal notifications are idempotent when provider and local
    state agree.
    """

    attempt = (
        PaymentAttempt.objects
        .get(pk=attempt.pk)
    )

    if not attempt.provider_payment_id:
        raise InvalidPaymentAttempt(
            "payment attempt has no provider payment id"
        )

    external = _get_external_payment_state(
        attempt=attempt,
    )

    return _reconcile_retail_payment_state(
        attempt=attempt,
        external=external,
    )


def _get_external_payment_state(
    *,
    attempt: PaymentAttempt,
) -> ExternalPaymentState:
    provider = get_default_hosted_payment_provider()

    external = provider.get_payment(
        provider_payment_id=(
            attempt.provider_payment_id
        ),
    )

    if (
        external.provider_payment_id
        != attempt.provider_payment_id
    ):
        raise PaymentReconciliationConflict(
            "provider returned a different payment id"
        )

    return external


def _reconcile_retail_payment_state(
    *,
    attempt: PaymentAttempt,
    external: ExternalPaymentState,
) -> PaymentAttempt:
    attempt.refresh_from_db()

    if external.status == ExternalPaymentStatus.PENDING:
        return attempt

    if external.status == ExternalPaymentStatus.SUCCEEDED:
        if attempt.status == PaymentAttempt.Status.SUCCEEDED:
            if (
                external.provider_transaction_id
                and attempt.provider_transaction_id
                and (
                    external.provider_transaction_id
                    != attempt.provider_transaction_id
                )
            ):
                raise PaymentReconciliationConflict(
                    "provider transaction id conflicts with local payment"
                )

            return attempt

        if attempt.status != PaymentAttempt.Status.PENDING:
            raise PaymentReconciliationConflict(
                "provider reports successful payment "
                f"for local {attempt.status} attempt"
            )

        complete_retail_payment(
            attempt=attempt,
            provider_transaction_id=(
                external.provider_transaction_id
            ),
        )

        attempt.refresh_from_db()

        return attempt

    if external.status == ExternalPaymentStatus.FAILED:
        if attempt.status in {
            PaymentAttempt.Status.FAILED,
            PaymentAttempt.Status.CANCELLED,
        }:
            return attempt

        if attempt.status == PaymentAttempt.Status.SUCCEEDED:
            raise PaymentReconciliationConflict(
                "provider reports failed payment "
                "for locally succeeded attempt"
            )

        return fail_retail_payment(
            attempt=attempt,
        )

    raise PaymentReconciliationConflict(
        f"unsupported external payment status: {external.status}"
    )


def _create_retail_hosted_payment_session(
    *,
    attempt: PaymentAttempt,
    customer_return_url: str,
    webhook_url: str,
) -> RetailPaymentRedirect:
    provider = get_default_hosted_payment_provider()

    session = create_hosted_payment_session(
        attempt=attempt,
        provider=provider,
        customer_return_url=customer_return_url,
        webhook_url=webhook_url,
    )

    attempt.refresh_from_db()

    return RetailPaymentRedirect(
        attempt=attempt,
        redirect_url=session.redirect_url,
    )
