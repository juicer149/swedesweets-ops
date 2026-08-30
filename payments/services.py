from __future__ import annotations

from django.db import transaction

from orders.models import Order
from payments.contracts import (
    HostedPaymentProvider,
    HostedPaymentRequest,
    HostedPaymentSession,
)
from payments.models import PaymentAttempt


class InvalidPaymentAttempt(ValueError):
    """Raised when payment attempt state violates a payment invariant."""


@transaction.atomic
def create_payment_attempt(
    *,
    order: Order,
) -> PaymentAttempt:
    """Create a payment attempt from the order's current price snapshot.

    The order row is locked so concurrent callers cannot both decide that
    there is no active payment attempt.

    No payment-provider interaction happens here.
    """

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    amount = order.total

    if amount is None:
        raise InvalidPaymentAttempt(
            "cannot create payment attempt for an unpriced order"
        )

    if amount <= 0:
        raise InvalidPaymentAttempt(
            "payment amount must be positive"
        )

    if PaymentAttempt.objects.filter(
        order=order,
        status=PaymentAttempt.Status.PENDING,
    ).exists():
        raise InvalidPaymentAttempt(
            f"order {order.pk} already has a pending payment attempt"
        )

    return PaymentAttempt.objects.create(
        order=order,
        amount=amount,
        currency=order.currency,
        status=PaymentAttempt.Status.PENDING,
    )


@transaction.atomic
def cancel_pending_payment_attempts_for_order(
    *,
    order: Order,
) -> None:
    """Cancel every pending payment attempt for an order."""

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    attempts = list(
        PaymentAttempt.objects
        .select_for_update()
        .filter(
            order=order,
            status=PaymentAttempt.Status.PENDING,
        )
        .order_by("id")
    )

    for attempt in attempts:
        attempt.status = PaymentAttempt.Status.CANCELLED
        attempt.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


@transaction.atomic
def mark_payment_attempt_succeeded(
    *,
    attempt: PaymentAttempt,
    provider_transaction_id: str | None = None,
) -> PaymentAttempt:
    """Move one pending payment attempt to SUCCEEDED."""

    attempt = (
        PaymentAttempt.objects
        .select_for_update()
        .get(pk=attempt.pk)
    )

    if attempt.status != PaymentAttempt.Status.PENDING:
        raise InvalidPaymentAttempt(
            "only pending payment attempts can succeed"
        )

    update_fields = [
        "status",
        "updated_at",
    ]

    if provider_transaction_id is not None:
        provider_transaction_id = (
            provider_transaction_id.strip()
        )

        if not provider_transaction_id:
            raise InvalidPaymentAttempt(
                "provider transaction id cannot be empty"
            )

        attempt.provider_transaction_id = (
            provider_transaction_id
        )
        update_fields.append(
            "provider_transaction_id"
        )

    attempt.status = PaymentAttempt.Status.SUCCEEDED
    attempt.save(
        update_fields=update_fields,
    )

    return attempt


@transaction.atomic
def mark_payment_attempt_failed(
    *,
    attempt: PaymentAttempt,
) -> PaymentAttempt:
    """Move one pending payment attempt to FAILED."""

    attempt = (
        PaymentAttempt.objects
        .select_for_update()
        .get(pk=attempt.pk)
    )

    if attempt.status != PaymentAttempt.Status.PENDING:
        raise InvalidPaymentAttempt(
            "only pending payment attempts can fail"
        )

    attempt.status = PaymentAttempt.Status.FAILED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return attempt


def create_hosted_payment_session(
    *,
    attempt: PaymentAttempt,
    provider: HostedPaymentProvider,
    customer_return_url: str,
    webhook_url: str,
) -> HostedPaymentSession:
    """Create and persist an external hosted payment session.

    External provider I/O deliberately happens outside a database transaction.

    The returned provider identifier is persisted only after the provider has
    successfully created the remote payment session.
    """

    attempt = (
        PaymentAttempt.objects
        .select_related("order")
        .get(pk=attempt.pk)
    )

    if attempt.status != PaymentAttempt.Status.PENDING:
        raise InvalidPaymentAttempt(
            "only pending payment attempts can create a hosted payment session"
        )

    if attempt.provider_payment_id:
        raise InvalidPaymentAttempt(
            "payment attempt already has a provider payment"
        )

    session = provider.create_payment(
        request=HostedPaymentRequest(
            reference=f"payment-{attempt.pk}",
            amount=attempt.amount,
            currency=attempt.currency,
            description=(
                f"SwedeSweets order {attempt.order_id}"
            ),
            customer_return_url=customer_return_url,
            webhook_url=webhook_url,
        ),
    )

    with transaction.atomic():
        locked_attempt = (
            PaymentAttempt.objects
            .select_for_update()
            .get(pk=attempt.pk)
        )

        if locked_attempt.status != PaymentAttempt.Status.PENDING:
            raise InvalidPaymentAttempt(
                "payment attempt changed state while provider payment was created"
            )

        if locked_attempt.provider_payment_id:
            raise InvalidPaymentAttempt(
                "payment attempt already has a provider payment"
            )

        locked_attempt.provider_payment_id = (
            session.provider_payment_id
        )
        locked_attempt.save(
            update_fields=[
                "provider_payment_id",
                "updated_at",
            ]
        )

    return session
