from __future__ import annotations

from accounts.roles import Capability, RoleSpec
from orders.models import Order

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


def can_create_order(*, role_spec: RoleSpec) -> bool:
    return role_spec.allows(Capability.CREATE_ORDERS)


def can_pack_order(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> bool:
    return order.status == Order.Status.PLACED and role_spec.allows(
        Capability.PACK_ORDERS
    )


def can_deliver_order(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> bool:
    return order.status == Order.Status.PACKED and role_spec.allows(
        Capability.DELIVER_ORDERS
    )


def can_edit_order(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> bool:
    return order.can_be_edited and role_spec.allows(Capability.EDIT_ORDERS)


def can_cancel_order(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> bool:
    return order.can_be_cancelled and role_spec.allows(Capability.CANCEL_ORDERS)
