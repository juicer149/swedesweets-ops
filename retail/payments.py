from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from payments.models import PaymentAttempt
from payments.providers.factory import (
    get_default_hosted_payment_provider,
)
from payments.services import (
    PaymentReconciliationConflict,
    create_hosted_payment_session,
    reconcile_payment_attempt,
)
from retail.models import RetailCheckoutSession
from retail.services import (
    complete_retail_payment,
    fail_retail_payment,
    start_retail_payment,
)


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
        provider = get_default_hosted_payment_provider()

        result = reconcile_payment_attempt(
            attempt=attempt,
            provider=provider,
            on_succeeded=complete_retail_payment,
            on_failed=fail_retail_payment,
        )
    except Exception:
        attempt.refresh_from_db()

        return RetailPaymentRecovery(
            attempt=attempt,
            action=RetailPaymentRecoveryAction.NEEDS_SUPPORT,
        )

    reconciled = result.attempt
    external = result.external

    redirect_url: str | None = None

    match reconciled.status:
        case PaymentAttempt.Status.SUCCEEDED:
            action = RetailPaymentRecoveryAction.CONFIRMED

        case PaymentAttempt.Status.FAILED | PaymentAttempt.Status.CANCELLED:
            action = RetailPaymentRecoveryAction.PAYMENT_FAILED

        case (
            PaymentAttempt.Status.PENDING
        ) if external.hosted_payment_url:
            action = RetailPaymentRecoveryAction.CONTINUE_PAYMENT
            redirect_url = external.hosted_payment_url

        case _:
            action = RetailPaymentRecoveryAction.NEEDS_SUPPORT

    return RetailPaymentRecovery(
        attempt=reconciled,
        action=action,
        redirect_url=redirect_url,
    )


def reconcile_retail_payment(
    *,
    attempt: PaymentAttempt,
) -> PaymentAttempt:
    """Reconcile one retail payment attempt against provider truth.

    Terminal outcomes are retail's own: a successful payment places the
    retail order, a failed payment releases its temporary reservations.
    """

    provider = get_default_hosted_payment_provider()

    result = reconcile_payment_attempt(
        attempt=attempt,
        provider=provider,
        on_succeeded=complete_retail_payment,
        on_failed=fail_retail_payment,
    )

    return result.attempt


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
