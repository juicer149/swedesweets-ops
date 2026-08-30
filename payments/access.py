from __future__ import annotations


AUTH_EXEMPT_VIEWS = frozenset(
    {
        "payments:sumup_webhook",
    }
)


VIEW_CAPABILITIES = {}
