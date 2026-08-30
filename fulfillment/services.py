from __future__ import annotations

from orders.models import Order
from orders.services import (
    cancel_order as cancel_shared_order,
    pack_order as pack_shared_order,
)
from reservations.policies import (
    consume_order_reservations_before_packing,
    release_order_reservations_before_cancellation,
)


def pack_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Pack an order using reservation-backed fulfillment."""

    return pack_shared_order(
        order=order,
        preparation=consume_order_reservations_before_packing,
        user=user,
    )


def cancel_order(
    *,
    order: Order,
    user=None,
    reason: str = "",
    note: str = "",
) -> Order:
    """Cancel an order and release reservation-backed fulfillment."""

    return cancel_shared_order(
        order=order,
        preparation=release_order_reservations_before_cancellation,
        user=user,
        reason=reason,
        note=note,
    )
