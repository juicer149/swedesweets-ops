from __future__ import annotations

from products.models import Product
from products.services import create_product


def product_factory(
    *,
    brand: str = "OLW",
    name: str = "Grill Chips",
    weight_per_unit: int = 275,
    stock_unit: str = Product.StockUnit.BOX,
    internal_number: int | None = None,
    manufacturer: str = "",
    vegan: bool = False,
) -> Product:
    result = create_product(
        brand=brand,
        name=name,
        weight_per_unit=weight_per_unit,
        stock_unit=stock_unit,
        internal_number=internal_number,
        manufacturer=manufacturer,
        vegan=vegan,
    )
    return result.item
