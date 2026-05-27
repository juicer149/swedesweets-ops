from __future__ import annotations


# Ops guardrail, not an inventory invariant.
# Adjust this if real customers can reasonably order more per product.
MAX_BOXES_PER_PRODUCT_PER_ORDER = 150


def is_unusually_large_order_line(*, boxes: int) -> bool:
    return boxes > MAX_BOXES_PER_PRODUCT_PER_ORDER
