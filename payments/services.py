from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

from orders.models import Order
from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
    HostedPaymentProvider,
    HostedPaymentRequest,
    HostedPaymentSession,
)
from payments.models import PaymentAttempt


class InvalidPaymentAttempt(ValueError):
    """Raised when payment attempt state violates a payment invariant."""


class PaymentReconciliationConflict(RuntimeError):
    """Provider truth conflicts with an irreversible local payment state."""


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


@dataclass(frozen=True, slots=True)
class PaymentReconciliationResult:
    """Outcome of reconciling one payment attempt against provider truth."""

    attempt: PaymentAttempt
    external: ExternalPaymentState


def reconcile_payment_attempt(
    *,
    attempt: PaymentAttempt,
    provider: HostedPaymentProvider,
    on_succeeded: Callable[..., object],
    on_failed: Callable[..., object],
) -> PaymentReconciliationResult:
    """Reconcile local payment state against provider-authoritative state.

    This function carries no channel knowledge and does not resolve its own
    provider, matching `create_hosted_payment_session`: the caller owns
    provider selection.

    Callers own what a successful or failed payment means for their own
    domain by supplying `on_succeeded`/`on_failed`, called with keyword
    arguments matching `mark_payment_attempt_succeeded`/
    `mark_payment_attempt_failed` (`attempt=`, and `provider_transaction_id=`
    for `on_succeeded`).

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
        provider=provider,
    )

    reconciled = _apply_reconciliation(
        attempt=attempt,
        external=external,
        on_succeeded=on_succeeded,
        on_failed=on_failed,
    )

    return PaymentReconciliationResult(
        attempt=reconciled,
        external=external,
    )


def _get_external_payment_state(
    *,
    attempt: PaymentAttempt,
    provider: HostedPaymentProvider,
) -> ExternalPaymentState:
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


def _apply_reconciliation(
    *,
    attempt: PaymentAttempt,
    external: ExternalPaymentState,
    on_succeeded: Callable[..., object],
    on_failed: Callable[..., object],
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

        on_succeeded(
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

        on_failed(
            attempt=attempt,
        )

        attempt.refresh_from_db()

        return attempt

    raise PaymentReconciliationConflict(
        f"unsupported external payment status: {external.status}"
    )
