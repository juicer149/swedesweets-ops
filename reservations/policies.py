from __future__ import annotations

from orders.errors import InvalidOrderOperation
from orders.models import Order
from reservations.services import (
    MissingReservations,
    cancel_reservations_for_order,
    consume_reservations_for_order,
    delete_reservations_for_order,
)


def consume_order_reservations_before_packing(
    *,
    order: Order,
) -> None:
    """Consume reserved stock before an order moves to PACKED."""

    try:
        consume_reservations_for_order(
            order=order,
        )
    except MissingReservations as exc:
        raise InvalidOrderOperation(
            f"Order {order.pk} has no reserved allocations"
        ) from exc


def release_order_reservations_before_cancellation(
    *,
    order: Order,
) -> None:
    """Release active reservations before an order is cancelled."""

    cancel_reservations_for_order(
        order=order,
    )


def clear_order_reservations_before_line_replacement(
    *,
    order: Order,
) -> None:
    """Remove active reservations before an order's lines are replaced."""

    delete_reservations_for_order(
        order=order,
    )
