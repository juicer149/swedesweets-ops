from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from products.models import Product


@dataclass(frozen=True)
class FormContextItem:
    label: str
    value: Any


def build_product_context_items(product: Product) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="SKU",
            value=product.sku,
        ),
        FormContextItem(
            label="Unit weight",
            value=product.unit_weight_label,
        ),
        FormContextItem(
            label="Stock unit",
            value=product.get_stock_unit_display(),
        ),
        FormContextItem(
            label="Current status",
            value="Active" if product.active else "Inactive",
        ),
    ]
