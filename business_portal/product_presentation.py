from __future__ import annotations

from products.localization import translated_product_name
from products.models import Product


def business_product_catalog_label(
    product: Product,
    *,
    language_code: str,
) -> str:
    return (
        f"{product.code_label} · "
        f"{translated_product_name(product, language_code=language_code)} · "
        f"{product.unit_weight_label}"
    )
