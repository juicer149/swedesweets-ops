from __future__ import annotations


AUTH_EXEMPT_VIEWS = frozenset(
    {
        "storefront:payment_return",
    }
)


VIEW_CAPABILITIES: dict[str, str] = {}
