from __future__ import annotations

from django.db import transaction

from orders.models import Order
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

    attempt.status = PaymentAttempt.Status.SUCCEEDED
    attempt.save(
        update_fields=[
            "status",
            "updated_at",
        ]
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
