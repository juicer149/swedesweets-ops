"""
Order data transfer objects.

public API:
    to_decimal(value: Quantity) -> Decimal
        -> Convert external numeric input into Decimal.

    OrderLineInput.units(...)
        -> Build an order-line input in product stock units.

    OrderLineInput.kg(...)
        -> Build an order-line input in kilograms.

    OrderLineInput.grams(...)
        -> Build an order-line input in grams.

    OrderLineInput.resolve_product_id() -> int
        -> Resolve either product_id or product into product id.

    PickLine
        -> Read model for packaging and packed-line selectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from orders.errors import InvalidOrderOperation
from products.models import Product
from products.units import ORDER_UNIT_GRAMS, ORDER_UNIT_KG, ORDER_UNIT_STOCK


Quantity = Decimal | int | float | str


def to_decimal(value: Quantity) -> Decimal:
    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


@dataclass(frozen=True)
class OrderLineInput:
    quantity: Decimal
    unit: str
    product_id: int | None = None
    product: Product | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", to_decimal(self.quantity))
        object.__setattr__(self, "unit", self.unit.strip().lower())

    @classmethod
    def units(
        cls,
        *,
        quantity: int,
        product: Product | None = None,
        product_id: int | None = None,
    ) -> Self:
        return cls(
            product=product,
            product_id=product_id,
            quantity=Decimal(quantity),
            unit=ORDER_UNIT_STOCK,
        )

    @classmethod
    def stock_units(
        cls,
        *,
        quantity: int,
        product: Product | None = None,
        product_id: int | None = None,
    ) -> Self:
        return cls.units(
            product=product,
            product_id=product_id,
            quantity=quantity,
        )

    @classmethod
    def kg(
        cls,
        *,
        kg: Decimal | str | int | float,
        product: Product | None = None,
        product_id: int | None = None,
    ) -> Self:
        return cls(
            product=product,
            product_id=product_id,
            quantity=Decimal(str(kg)),
            unit=ORDER_UNIT_KG,
        )

    @classmethod
    def grams(
        cls,
        *,
        grams: int,
        product: Product | None = None,
        product_id: int | None = None,
    ) -> Self:
        return cls(
            product=product,
            product_id=product_id,
            quantity=Decimal(grams),
            unit=ORDER_UNIT_GRAMS,
        )

    def resolve_product_id(self) -> int:
        if self.product_id is not None and self.product is not None:
            if self.product_id != self.product.id:
                raise InvalidOrderOperation(
                    f"product_id ({self.product_id}) and "
                    f"product ({self.product.id}) refer to different products"
                )

        if self.product_id is not None:
            return self.product_id

        if self.product is not None:
            return self.product.id

        raise InvalidOrderOperation("product_id or product is required")


@dataclass(frozen=True)
class PickLine:
    sku: str
    product_name: str
    batch_id: str
    location: str
    quantity: int
    quantity_label: str
