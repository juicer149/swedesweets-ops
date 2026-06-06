"""
Route access policy.

This module answers:

    What capability is required to reach this view?

Views are denied by default unless listed here or marked public.
"""

from __future__ import annotations

from accounts.roles import Capability


PUBLIC_VIEWS = frozenset(
    {
        "login",
        "logout",
        "password_change",
        "password_change_done",
        "password_reset",
        "password_reset_done",
        "password_reset_confirm",
        "password_reset_complete",
    }
)


VIEW_CAPABILITIES: dict[str, Capability] = {
    # Root/dashboard
    "index": Capability.VIEW_STAFF_OPS,

    # Orders
    "orders:index": Capability.VIEW_ORDERS,
    "orders:detail": Capability.VIEW_ORDERS,
    "orders:create": Capability.CREATE_ORDERS,
    "orders:edit": Capability.EDIT_ORDERS,
    "orders:cancel": Capability.CANCEL_ORDERS,
    "orders:pack": Capability.PACK_ORDERS,
    "orders:deliver": Capability.DELIVER_ORDERS,

    # Inventory
    "inventory:index": Capability.VIEW_INVENTORY,
    "inventory:detail": Capability.VIEW_INVENTORY,
    "inventory:create": Capability.CREATE_BATCHES,
    "inventory:edit": Capability.EDIT_BATCHES,
    "inventory:close": Capability.CLOSE_BATCHES,

    # Products / internal ops product master
    "products:index": Capability.VIEW_OPS_PRODUCTS,
    "products:detail": Capability.VIEW_OPS_PRODUCTS,
    "products:create": Capability.CREATE_PRODUCTS,
    "products:edit": Capability.EDIT_PRODUCTS,

    # Customers / internal ops customer master
    "customers:index": Capability.VIEW_CUSTOMERS,
    "customers:detail": Capability.VIEW_CUSTOMERS,
    "customers:create": Capability.CREATE_CUSTOMERS,
    "customers:edit": Capability.EDIT_CUSTOMERS,
}


EXEMPT_PATH_PREFIXES = (
    "/admin/",
    "/static/",
    "/favicon.ico",
)
