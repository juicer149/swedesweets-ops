from __future__ import annotations

from accounts.roles import Capability


CAPABILITIES = frozenset(
    {
        Capability.VIEW_ORDERS,
        Capability.CREATE_ORDERS,
        Capability.EDIT_ORDERS,
        Capability.CANCEL_ORDERS,
        Capability.PACK_ORDERS,
        Capability.DELIVER_ORDERS,
    }
)


VIEW_CAPABILITIES = {
    "orders:index": Capability.VIEW_ORDERS,
    "orders:detail": Capability.VIEW_ORDERS,
    "orders:create": Capability.CREATE_ORDERS,
    "orders:edit": Capability.EDIT_ORDERS,
    "orders:cancel": Capability.CANCEL_ORDERS,
    "orders:pack": Capability.PACK_ORDERS,
    "orders:deliver": Capability.DELIVER_ORDERS,
}
