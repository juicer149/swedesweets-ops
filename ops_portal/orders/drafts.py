from __future__ import annotations

from collections.abc import Iterable

from business.datatypes import BusinessOfferLineInput
from business.drafts import (
    buyer_from_customer,
    resolve_business_offer_lines,
)
from customers.models import Customer
from orders.drafts import OrderDraft
from orders.errors import InvalidOrderOperation
from orders.models import Order


def build_ops_order_draft(
    *,
    customer: Customer,
    lines: Iterable[BusinessOfferLineInput],
) -> OrderDraft:
    """Build a BUSINESS order draft from explicit commercial offers."""

    resolved_lines = resolve_business_offer_lines(
        lines=lines,
    )

    if not resolved_lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    return OrderDraft(
        channel=Order.Channel.BUSINESS,
        currency=Order.Currency.EUR,
        customer=customer,
        buyer=buyer_from_customer(
            customer=customer,
        ),
        lines=resolved_lines,
    )
