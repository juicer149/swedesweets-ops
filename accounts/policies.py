from __future__ import annotations


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


VIEW_CAPABILITIES = {
    # Root/dashboard
    "index": "can_view_staff_ops",

    # Orders
    "orders:index": "can_view_orders",
    "orders:detail": "can_view_orders",
    "orders:create": "can_create_orders",
    "orders:edit": "can_edit_orders",
    "orders:cancel": "can_cancel_orders",
    "orders:pack": "can_pack_orders",
    "orders:deliver": "can_deliver_orders",

    # Inventory
    "inventory:index": "can_view_inventory",
    "inventory:detail": "can_view_inventory",
    "inventory:create": "can_create_batches",
    "inventory:edit": "can_edit_batches",
    "inventory:close": "can_close_batches",

    # Products / internal ops product master
    "products:index": "can_view_ops_products",
    "products:detail": "can_view_ops_products",
    "products:create": "can_create_products",
    "products:edit": "can_edit_products",

    # Customers / internal ops customer master
    "customers:index": "can_view_customers",
    "customers:detail": "can_view_customers",
    "customers:create": "can_create_customers",
    "customers:edit": "can_edit_customers",
}


EXEMPT_PATH_PREFIXES = (
    "/admin/",
    "/static/",
    "/favicon.ico",
)
