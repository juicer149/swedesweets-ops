"""Fulfillment read selectors.

Composes reservation data into the pack/pick views used by fulfillment
workflows. Reservation state itself is owned by ``reservations``.
"""

from __future__ import annotations

from fulfillment.datatypes import PickLine
from orders.models import Order
from reservations.datatypes import ReservationPick
from reservations.selectors import (
    list_consumed_picks_for_order,
    list_reserved_picks_for_order,
)


def get_packaging_list(
    *,
    order: Order,
) -> list[PickLine]:
    picks = list_reserved_picks_for_order(
        order=order,
    )

    return [
        _build_pick_line(
            pick=pick,
        )
        for pick in picks
    ]


def get_packed_lines(
    *,
    order: Order,
) -> list[PickLine]:
    picks = list_consumed_picks_for_order(
        order=order,
    )

    return [
        _build_pick_line(
            pick=pick,
        )
        for pick in picks
    ]


def _build_pick_line(
    *,
    pick: ReservationPick,
) -> PickLine:
    return PickLine(
        allocation_id=pick.allocation_id,
        sku=pick.sku,
        product_name=pick.product_name,
        batch_id=pick.batch_code,
        location=pick.location,
        quantity=pick.quantity,
        quantity_label=pick.quantity_label,
    )
