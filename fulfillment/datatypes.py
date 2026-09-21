"""Fulfillment data transfer objects.

public API:
    PickLine
        -> Read model for the packing checklist and packed-line views.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PickLine:
    allocation_id: int
    sku: str
    product_name: str
    batch_id: str
    location: str
    quantity: int
    quantity_label: str
