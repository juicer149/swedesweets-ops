from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from common.navbar_cart import (
    NavbarCart,
    NavbarCartLine,
)
from retail.models import RetailCart


def build_retail_navbar_cart(
    *,
    cart: RetailCart | None,
) -> NavbarCart:
    if cart is None:
        return _empty_retail_navbar_cart()

    cart_lines = tuple(
        cart.lines
        .select_related(
            "commercial_price__product",
        )
        .order_by("id")
    )

    if not cart_lines:
        return _empty_retail_navbar_cart()

    lines = tuple(
        _build_retail_navbar_cart_line(
            line=line,
        )
        for line in cart_lines
    )

    return NavbarCart(
        aria_label=_("Shopping cart"),
        title=_("Shopping cart"),
        line_count=len(lines),
        lines=lines,
        fragment_url=reverse(
            "storefront:navbar_cart_fragment"
        ),
        proceed_label=_("Continue shopping"),
        proceed_url=reverse(
            "storefront:product_list"
        ),
        empty_message=_(
            "Your cart is empty."
        ),
        empty_action_label=_(
            "Browse shop"
        ),
        empty_action_url=reverse(
            "storefront:product_list"
        ),
    )


def _empty_retail_navbar_cart() -> NavbarCart:
    return NavbarCart(
        aria_label=_("Shopping cart"),
        title=_("Shopping cart"),
        line_count=0,
        lines=(),
        fragment_url=reverse(
            "storefront:navbar_cart_fragment"
        ),
        proceed_label=_("Continue shopping"),
        proceed_url=reverse(
            "storefront:product_list"
        ),
        empty_message=_(
            "Your cart is empty."
        ),
        empty_action_label=_(
            "Browse shop"
        ),
        empty_action_url=reverse(
            "storefront:product_list"
        ),
    )


def _build_retail_navbar_cart_line(
    *,
    line,
) -> NavbarCartLine:
    product = (
        line.commercial_price.product
    )

    metadata = tuple(
        value
        for value in (
            line.commercial_price.get_reason_display()
            if line.commercial_price.reason
            else None,
        )
        if value
    )

    return NavbarCartLine(
        line_id=line.id,
        label=product.display_name,
        product_url=reverse(
            "storefront:product_detail",
            kwargs={
                "product_id": product.id,
            },
        ),
        metadata=metadata,
        quantity=line.quantity,
        quantity_url=reverse(
            "storefront:set_cart_line_quantity",
            kwargs={
                "cart_line_id": line.id,
            },
        ),
        remove_url=reverse(
            "storefront:remove_cart_line",
            kwargs={
                "cart_line_id": line.id,
            },
        ),
    )
