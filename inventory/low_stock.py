from __future__ import annotations

from typing import Protocol


LOW_STOCK_THRESHOLD = 6


class StockAvailabilityRow(Protocol):
    available_boxes: int


def is_low_stock(
    *,
    available_boxes: int,
    threshold: int = LOW_STOCK_THRESHOLD,
) -> bool:
    return available_boxes <= threshold
