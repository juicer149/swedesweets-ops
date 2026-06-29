from __future__ import annotations

from typing import Protocol

LOW_STOCK_THRESHOLD = 6


class StockAvailabilityRow(Protocol):
    available_quantity: int


def is_low_stock(
    *,
    available_quantity: int,
    threshold: int = LOW_STOCK_THRESHOLD,
) -> bool:
    return available_quantity <= threshold
