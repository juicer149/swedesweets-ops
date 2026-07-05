"""
Product unit conversion.

public API:
    normalize_order_unit(unit: str) -> OrderUnit 
        -> Normalize and validate external order unit.

    quantity_to_units(
        *,
        product: Product,
        quantity: Decimal,
        unit: str,
    ) -> int
        -> Convert external order quantity to whole product stock units.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from products.errors import InvalidProductData, UnsupportedOrderUnit
from products.models import Product


class OrderUnit(StrEnum):
    STOCK = "stock_unit"
    KG = "kg"
    GRAMS = "grams"


def normalize_order_unit(unit: str | OrderUnit) -> OrderUnit:
    try:
        return OrderUnit(str(unit).strip().lower())
    except ValueError as exc:
        raise UnsupportedOrderUnit(f"Unsupported order unit: {unit}") from exc


def quantity_to_units(
    *,
    product: Product,
    quantity: Decimal,
    unit: str | OrderUnit,
) -> int:
    """Convert external order quantity into whole product stock units.

    External order input may use stock_unit, kg, or grams. Internal fulfillment
    quantity is always whole stock units for the selected product.
    """

    unit = normalize_order_unit(unit)

    if quantity <= 0:
        raise InvalidProductData("quantity must be positive")

    match unit:
        case OrderUnit.STOCK:
            if quantity != quantity.to_integral_value():
                raise InvalidProductData("stock unit orders must use a whole number")

            return int(quantity)

        case OrderUnit.GRAMS:
            if quantity != quantity.to_integral_value():
                raise InvalidProductData("gram orders must use a whole number")

            return product.grams_to_units(grams=int(quantity))

        case OrderUnit.KG:
            return product.kg_to_units(kg=quantity)

    raise UnsupportedOrderUnit(f"Unsupported order unit: {unit}")
