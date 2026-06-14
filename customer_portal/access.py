from __future__ import annotations

from accounts.roles import Capability

VIEW_CAPABILITIES = {
    "customer_portal:index": Capability.VIEW_CUSTOMER_PORTAL,
    "customer_portal:orders": Capability.VIEW_OWN_ORDERS,
    "customer_portal:order_detail": Capability.VIEW_OWN_ORDERS,
    "customer_portal:profile": Capability.VIEW_OWN_ACCOUNT,
    "customer_portal:edit_profile": Capability.EDIT_OWN_ACCOUNT,
}
