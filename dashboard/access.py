from __future__ import annotations

from accounts.roles import Capability

CAPABILITIES = frozenset(
    {
        Capability.VIEW_STAFF_OPS,
    }
)


VIEW_CAPABILITIES = {
    "index": Capability.VIEW_STAFF_OPS,
}
