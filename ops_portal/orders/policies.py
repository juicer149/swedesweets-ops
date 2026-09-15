from __future__ import annotations

from inventory.errors import InsufficientStockError
from inventory.selectors import list_orderable_batches_for_product
from orders.errors import InvalidOrderOperation
from orders.models import Order
from reservations.planning import InsufficientReservationCapacity
from reservations.services import reserve_order_line_from_pool


def prepare_ops_order_for_placement(
    *,
    order: Order,
) -> None:
    """Reserve inventory for an order placed/edited from the ops portal.

    Ops orders never carry a BusinessOfferSelection - they are always
    ordinary legacy lines, regardless of the order's channel (Business or
    Retail). This is the ordinary-FEFO branch of
    business.prepare_business_order_for_placement, extracted so
    ops_portal never has to import from business - offer-aware catalog
    pricing simply does not apply to an order built from the ops portal.
    """

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
