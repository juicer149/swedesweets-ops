"""
Product unit conversion.

public API:
    normalize_order_unit(unit: str) -> str
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

from products.errors import InvalidProductData, UnsupportedOrderUnit
from products.models import Product


#TODO: consider have a strenum to keep all of these in one place
ORDER_UNIT_STOCK = "stock_unit"
ORDER_UNIT_KG = "kg"
ORDER_UNIT_GRAMS = "grams"

SUPPORTED_ORDER_UNITS = {
    ORDER_UNIT_STOCK,
    ORDER_UNIT_KG,
    ORDER_UNIT_GRAMS,
}


def normalize_order_unit(unit: str) -> str:
    normalized_unit = unit.strip().lower()

    if normalized_unit not in SUPPORTED_ORDER_UNITS:
        raise UnsupportedOrderUnit(f"Unsupported order unit: {unit}")

    return normalized_unit


def quantity_to_units(
    *,
    product: Product,
    quantity: Decimal,
    unit: str,
) -> int:
    """Convert external order quantity into whole product stock units.

    External order input may use stock_unit, kg, or grams. Internal fulfillment
    quantity is always whole stock units for the selected product.
    """

    unit = normalize_order_unit(unit)

    if quantity <= 0:
        raise InvalidProductData("quantity must be positive")

    if unit == ORDER_UNIT_STOCK:
        if quantity != quantity.to_integral_value():
            raise InvalidProductData(
                "stock unit orders must use a whole number"
            )

        return int(quantity)

    if unit == ORDER_UNIT_GRAMS:
        if quantity != quantity.to_integral_value():
            raise InvalidProductData("gram orders must use a whole number")

        return product.grams_to_units(grams=int(quantity))

    if unit == ORDER_UNIT_KG:
        return product.kg_to_units(kg=quantity)

    raise UnsupportedOrderUnit(f"Unsupported order unit: {unit}")
