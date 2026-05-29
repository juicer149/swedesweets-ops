from __future__ import annotations

from datetime import date

from inventory.models import InventoryBatch
from inventory.services import create_batch
from products.models import Product


def batch_factory(
    *,
    product: Product,
    today: date,
    batch_id: str = "A-001",
    quantity: int = 10,
    best_before: date | None = None,
    location: str = "Shelf A1",
) -> InventoryBatch:
    return create_batch(
        batch_id=batch_id,
        product=product,
        quantity=quantity,
        best_before=best_before or date(2026, 6, 1),
        location=location,
        today=today,
    )
