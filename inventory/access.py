from __future__ import annotations

from accounts.roles import Capability


CAPABILITIES = frozenset(
    {
        Capability.VIEW_INVENTORY,
        Capability.CREATE_BATCHES,
        Capability.EDIT_BATCHES,
        Capability.CLOSE_BATCHES,
        Capability.VIEW_INVENTORY_RISKS,
    }
)


VIEW_CAPABILITIES = {
    "inventory:index": Capability.VIEW_INVENTORY,
    "inventory:detail": Capability.VIEW_INVENTORY,
    "inventory:create": Capability.CREATE_BATCHES,
    "inventory:edit": Capability.EDIT_BATCHES,
    "inventory:close": Capability.CLOSE_BATCHES,
}
