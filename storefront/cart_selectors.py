from __future__ import annotations

from uuid import UUID

from retail.models import (
    RetailCart,
    RetailCartLine,
)


def get_retail_cart(
    *,
    cart_id: UUID | None,
) -> RetailCart | None:
    if cart_id is None:
        return None

    return (
        RetailCart.objects
        .prefetch_related(
            "lines__commercial_price__product",
        )
        .filter(
            pk=cart_id,
        )
        .first()
    )


def get_retail_cart_line(
    *,
    cart: RetailCart,
    line_id: int,
) -> RetailCartLine | None:
    return (
        RetailCartLine.objects
        .select_related(
            "commercial_price__product",
        )
        .filter(
            pk=line_id,
            cart=cart,
        )
        .first()
    )
