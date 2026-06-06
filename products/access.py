from __future__ import annotations

from accounts.roles import Capability


CAPABILITIES = frozenset(
    {
        Capability.VIEW_OPS_PRODUCTS,
        Capability.CREATE_PRODUCTS,
        Capability.EDIT_PRODUCTS,
    }
)


VIEW_CAPABILITIES = {
    "products:index": Capability.VIEW_OPS_PRODUCTS,
    "products:detail": Capability.VIEW_OPS_PRODUCTS,
    "products:create": Capability.CREATE_PRODUCTS,
    "products:edit": Capability.EDIT_PRODUCTS,
}
