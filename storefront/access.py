from __future__ import annotations


AUTH_EXEMPT_VIEWS = frozenset(
    {
        "index",
        "storefront:product_list",
        "storefront:product_detail",
        "storefront:add_to_cart",
        "storefront:navbar_cart_fragment",
        "storefront:set_cart_line_quantity",
        "storefront:remove_cart_line",
        "storefront:payment_return",
        "public_site:contact",
        "public_site:faq",
    }
)


VIEW_CAPABILITIES: dict[str, str] = {}
