from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inventory.models import InventoryBatch


@dataclass(frozen=True)
class FormContextItem:
    label: str
    value: Any


def build_batch_context_items(batch: InventoryBatch) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="Product",
            value=batch.product.catalog_label,
        ),
        FormContextItem(
            label="Status",
            value=batch.get_status_display(),
        ),
        FormContextItem(
            label="Location",
            value=batch.location,
        ),
    ]

def build_close_batch_context_items(batch: InventoryBatch) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="Product",
            value=batch.product.catalog_label,
        ),
        FormContextItem(
            label="Quantity",
            value=batch.product.stock_quantity_label(batch.quantity),
        ),
        FormContextItem(
            label="Status",
            value=batch.get_status_display(),
        ),
    ]
