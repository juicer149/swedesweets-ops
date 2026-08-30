from __future__ import annotations

from collections.abc import Iterable

from customers.models import Customer
from orders.datatypes import OrderLineInput
from orders.models import Order
from orders.services import (
    create_order as create_shared_order,
    place_order as place_shared_order,
    update_placed_order as update_shared_placed_order,
)

from business.policies import (
    prepare_business_order_for_placement,
)


def create_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Create and immediately place an ordinary business order."""

    return create_shared_order(
        customer=customer,
        lines=lines,
        preparation=prepare_business_order_for_placement,
        user=user,
    )


def place_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Place an ordinary business draft order."""

    return place_shared_order(
        order=order,
        preparation=prepare_business_order_for_placement,
        user=user,
    )


def update_placed_order(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace lines and rebuild an ordinary business reservation."""

    return update_shared_placed_order(
        order=order,
        lines=lines,
        preparation=prepare_business_order_for_placement,
        user=user,
    )
