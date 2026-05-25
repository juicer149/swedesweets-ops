"""
Product unit conversion.

public API:
    normalize_order_unit(unit: str) -> str
        -> Normalize and validate external order unit.

    quantity_to_boxes(
        *,
        product: Product,
        quantity: Decimal,
        unit: str,
    ) -> int
        -> Convert external order quantity to whole boxes.
"""

from __future__ import annotations

from decimal import Decimal

from products.errors import InvalidProductData, UnsupportedOrderUnit
from products.models import Product


SUPPORTED_ORDER_UNITS = {"boxes", "kg", "grams"}


def normalize_order_unit(unit: str) -> str:
    normalized_unit = unit.strip().lower()

    if normalized_unit not in SUPPORTED_ORDER_UNITS:
        raise UnsupportedOrderUnit(f"Unsupported order unit: {unit}")

    return normalized_unit


def quantity_to_boxes(
    *,
    product: Product,
    quantity: Decimal,
    unit: str,
) -> int:
    """Convert external order quantity into whole boxes.

    External order input may use boxes, kg, or grams.
    Internal warehouse quantity is always boxes.
    """

    unit = normalize_order_unit(unit)

    if quantity <= 0:
        raise InvalidProductData("quantity must be positive")

    if unit == "boxes":
        if quantity != quantity.to_integral_value():
            raise InvalidProductData("box orders must use a whole number")

        return int(quantity)

    if unit == "grams":
        if quantity != quantity.to_integral_value():
            raise InvalidProductData("gram orders must use a whole number")

        return product.grams_to_boxes(grams=int(quantity))

    if unit == "kg":
        return product.kg_to_boxes(kg=quantity)

    raise UnsupportedOrderUnit(f"Unsupported order unit: {unit}")
