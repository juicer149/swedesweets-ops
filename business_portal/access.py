from __future__ import annotations

from accounts.roles import Capability

VIEW_CAPABILITIES = {
    "business_portal:index": Capability.VIEW_CUSTOMER_PORTAL,
    "business_portal:orders": Capability.VIEW_OWN_ORDERS,
    "business_portal:order_detail": Capability.VIEW_OWN_ORDERS,
    "business_portal:place_order": Capability.PLACE_CUSTOMER_ORDERS,
    "business_portal:review_order": Capability.PLACE_CUSTOMER_ORDERS,
    "business_portal:catalog": Capability.VIEW_CUSTOMER_PORTAL,
    "business_portal:profile": Capability.VIEW_OWN_ACCOUNT,
    "business_portal:edit_profile": Capability.EDIT_OWN_ACCOUNT,
    "business_portal:contact": Capability.VIEW_CUSTOMER_PORTAL,
}
