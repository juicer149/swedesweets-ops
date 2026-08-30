from __future__ import annotations

from inventory.errors import InsufficientStockError
from inventory.selectors import (
    list_orderable_batches_for_product,
)
from orders.errors import InvalidOrderOperation
from orders.models import Order
from reservations.planning import (
    InsufficientReservationCapacity,
)
from reservations.services import (
    reserve_order_line_from_pool,
)


def prepare_business_order_for_placement(
    *,
    order: Order,
) -> None:
    """Reserve ordinary sellable inventory before placing a business order.

    Business owns inventory eligibility policy.

    Reservations owns locking, active-reservation accounting, FEFO planning
    and persistence.
    """

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "Business placement policy requires a business order"
        )

    lines = list(
        order.lines
        .select_related("product")
        .order_by("id")
    )

    if not lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    for line in lines:
        batches = list_orderable_batches_for_product(
            product=line.product,
        )

        try:
            reserve_order_line_from_pool(
                order_line=line,
                batches=batches,
                quantity=line.quantity_in_units,
                reserved_until=None,
            )
        except InsufficientReservationCapacity as exc:
            raise InsufficientStockError(
                product_name=line.product.display_name,
                requested_quantity=exc.requested_quantity,
                available_quantity=exc.available_quantity,
                missing_quantity=exc.missing_quantity,
            ) from exc
