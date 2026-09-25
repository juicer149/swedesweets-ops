from __future__ import annotations

from inventory.errors import InsufficientStockError
from orders.errors import InvalidOrderOperation
from orders.models import Order, OrderLine
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import list_orderable_batches_for_offer
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
    """Reserve inventory according to each line's commercial offer.

    OrderLine.commercial_offer is the durable commercial identity.

    Business owns commercial eligibility. Pricing derives the physical
    stock pool represented by an offer. Reservations owns locking,
    accounting, FEFO planning and persistence.
    """

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "Business placement policy requires a business order"
        )

    lines = list(
        order.lines
        .select_related(
            "product",
            "commercial_offer",
        )
        .prefetch_related(
            "commercial_offer__amounts",
        )
        .order_by("id")
    )

    if not lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    for line in lines:
        offer = line.commercial_offer

        _validate_business_offer(
            line=line,
            offer=offer,
        )

        batches = list_orderable_batches_for_offer(
            offer=offer,
            currency=PriceAmount.Currency.EUR,
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


def _validate_business_offer(
    *,
    line: OrderLine,
    offer: CommercialPrice,
) -> None:
    if offer.product_id != line.product_id:
        raise InvalidOrderOperation(
            "commercial offer does not belong to the order-line product"
        )

    if offer.channel != CommercialPrice.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "commercial offer does not belong to the business channel"
        )

    if not line.product.active or not offer.enabled:
        raise InvalidOrderOperation(
            "selected business offer is no longer available"
        )

    if (
        offer.batch_id is not None
        and not any(
            amount.currency == PriceAmount.Currency.EUR
            for amount in offer.amounts.all()
        )
    ):
        raise InvalidOrderOperation(
            "selected business batch offer is no longer available"
        )
