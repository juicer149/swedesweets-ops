from __future__ import annotations

from accounts.roles import Capability


CAPABILITIES = frozenset(
    {
        Capability.VIEW_CUSTOMERS,
        Capability.CREATE_CUSTOMERS,
        Capability.EDIT_CUSTOMERS,
    }
)


VIEW_CAPABILITIES = {
    "customers:index": Capability.VIEW_CUSTOMERS,
    "customers:detail": Capability.VIEW_CUSTOMERS,
    "customers:create": Capability.CREATE_CUSTOMERS,
    "customers:edit": Capability.EDIT_CUSTOMERS,
}
