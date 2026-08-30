from __future__ import annotations

from dataclasses import dataclass

from payments.models import PaymentAttempt
from payments.providers.factory import (
    get_default_hosted_payment_provider,
)
from payments.services import create_hosted_payment_session
from retail.models import RetailCheckoutSession
from retail.services import start_retail_payment


@dataclass(frozen=True, slots=True)
class RetailPaymentRedirect:
    attempt: PaymentAttempt
    redirect_url: str


def begin_retail_hosted_payment(
    *,
    checkout: RetailCheckoutSession,
    customer_return_url: str,
    webhook_url: str,
) -> RetailPaymentRedirect:
    """Start a retail payment and create its external hosted checkout.

    The local payment start commits before any provider HTTP request occurs.

    If provider creation fails, the pending PaymentAttempt and its temporary
    reservations remain intact so provider initialization may be retried.
    """

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
    """Retry provider initialization for an existing payment attempt.

    This does not create another PaymentAttempt and does not replace the
    existing temporary reservations.

    The payment service itself rejects attempts that are no longer pending or
    that already have a provider payment identifier.
    """

    return _create_retail_hosted_payment_session(
        attempt=attempt,
        customer_return_url=customer_return_url,
        webhook_url=webhook_url,
    )


def _create_retail_hosted_payment_session(
    *,
    attempt: PaymentAttempt,
    customer_return_url: str,
    webhook_url: str,
) -> RetailPaymentRedirect:
    """Create the external hosted checkout for one local payment attempt."""

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
