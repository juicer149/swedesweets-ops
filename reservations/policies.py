from __future__ import annotations

from orders.errors import InvalidOrderOperation
from orders.models import Order
from reservations.services import (
    MissingReservations,
    consume_reservations_for_order,
)


def consume_order_reservations_before_packing(
    *,
    order: Order,
) -> None:
    """Consume reserved stock before an order moves to PACKED.

    This policy expresses the current fulfillment rule:

    an order may be packed only by consuming its existing reservations.

    The reservation service owns locking and physical stock mutation.
    """

    try:
        consume_reservations_for_order(
            order=order,
        )
    except MissingReservations as exc:
        raise InvalidOrderOperation(
            f"Order {order.pk} has no reserved allocations"
        ) from exc
