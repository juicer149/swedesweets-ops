from __future__ import annotations


AUTH_EXEMPT_VIEWS = frozenset(
    {
        "storefront:product_list",
        "storefront:product_detail",
        "storefront:add_to_cart",
        "storefront:payment_return",
    }
)


VIEW_CAPABILITIES: dict[str, str] = {}
