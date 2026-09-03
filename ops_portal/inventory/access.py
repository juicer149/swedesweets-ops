from __future__ import annotations

from accounts.roles import Capability, RoleSpec
from inventory.models import InventoryBatch

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
    "ops_inventory:index": Capability.VIEW_INVENTORY,
    "ops_inventory:detail": Capability.VIEW_INVENTORY,
    "ops_inventory:create": Capability.CREATE_BATCHES,
    "ops_inventory:edit": Capability.EDIT_BATCHES,
    "ops_inventory:close": Capability.CLOSE_BATCHES,
}


def can_create_batch(*, role_spec: RoleSpec) -> bool:
    return role_spec.allows(Capability.CREATE_BATCHES)


def can_edit_batch(
    *,
    batch: InventoryBatch,
    role_spec: RoleSpec,
) -> bool:
    return batch.status != InventoryBatch.Status.CLOSED and role_spec.allows(
        Capability.EDIT_BATCHES
    )


def can_close_batch(
    *,
    batch: InventoryBatch,
    role_spec: RoleSpec,
) -> bool:
    return batch.status != InventoryBatch.Status.CLOSED and role_spec.allows(
        Capability.CLOSE_BATCHES
    )
