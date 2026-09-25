from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from orders.datatypes import to_decimal
from products.units import OrderUnit, normalize_order_unit


@dataclass(frozen=True, slots=True)
class BusinessOfferLineInput:
    """One explicitly selected BUSINESS commercial offer."""

    commercial_offer_id: int
    quantity: Decimal
    unit: OrderUnit

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "quantity",
            to_decimal(self.quantity),
        )
        object.__setattr__(
            self,
            "unit",
            normalize_order_unit(self.unit),
        )
