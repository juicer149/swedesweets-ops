from __future__ import annotations

from orders.models import Order
from orders.services import (
    pack_order as pack_shared_order,
)
from reservations.policies import (
    consume_order_reservations_before_packing,
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
