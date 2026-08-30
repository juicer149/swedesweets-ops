from __future__ import annotations

from payments.models import PaymentAttempt


def list_pending_payment_attempt_ids(
    *,
    provider: str,
    order_channel: str,
) -> list[int]:
    """Return pending payment attempt ids in stable processing order.

    The ids are materialized before provider I/O begins so a database cursor
    is not held open while external network requests are performed.
    """

    return list(
        PaymentAttempt.objects
        .filter(
            provider=provider,
            status=PaymentAttempt.Status.PENDING,
            order__channel=order_channel,
        )
        .order_by("id")
        .values_list(
            "id",
            flat=True,
        )
    )
