from __future__ import annotations

from products.models import Product
from products.services import create_product


def product_factory(
    *,
    brand: str = "OLW",
    name: str = "Grill Chips",
    weight_per_box: int = 275,
    internal_number: int | None = None,
    manufacturer: str = "",
    vegan: bool = False,
) -> Product:
    result = create_product(
        brand=brand,
        name=name,
        weight_per_box=weight_per_box,
        internal_number=internal_number,
        manufacturer=manufacturer,
        vegan=vegan,
    )
    return result.item
