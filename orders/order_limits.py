from __future__ import annotations


# Ops guardrail, not an inventory invariant.
# Adjust this if real customers can reasonably order more per product.
MAX_QUANTITY_PER_PRODUCT_PER_ORDER = 1000 


def is_unusually_large_order_line(*, quantity: int) -> bool:
    return quantity > MAX_QUANTITY_PER_PRODUCT_PER_ORDER
