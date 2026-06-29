"""
Route access policy.

This module answers:

    What capability is required to reach this view?

Each app declares the access policy for the views it owns in its own
access.py module. This module aggregates those declarations into the policy map
used by ViewCapabilityMiddleware.

Views are denied by default unless listed here or marked auth-exempt.
"""

from __future__ import annotations

from accounts.access import (
    AUTH_EXEMPT_VIEWS as ACCOUNT_AUTH_EXEMPT_VIEWS,
)
from accounts.access import (
    VIEW_CAPABILITIES as ACCOUNT_VIEW_CAPABILITIES,
)
from customer_portal.access import (
    VIEW_CAPABILITIES as CUSTOMER_PORTAL_VIEW_CAPABILITIES,
)
from customers.access import VIEW_CAPABILITIES as CUSTOMER_VIEW_CAPABILITIES
from dashboard.access import VIEW_CAPABILITIES as DASHBOARD_VIEW_CAPABILITIES
from inventory.access import VIEW_CAPABILITIES as INVENTORY_VIEW_CAPABILITIES
from orders.access import VIEW_CAPABILITIES as ORDER_VIEW_CAPABILITIES
from products.access import VIEW_CAPABILITIES as PRODUCT_VIEW_CAPABILITIES

AUTH_EXEMPT_VIEWS = ACCOUNT_AUTH_EXEMPT_VIEWS


VIEW_CAPABILITIES = {
    **DASHBOARD_VIEW_CAPABILITIES,
    **ACCOUNT_VIEW_CAPABILITIES,
    **ORDER_VIEW_CAPABILITIES,
    **INVENTORY_VIEW_CAPABILITIES,
    **PRODUCT_VIEW_CAPABILITIES,
    **CUSTOMER_VIEW_CAPABILITIES,
    **CUSTOMER_PORTAL_VIEW_CAPABILITIES,
}


EXEMPT_PATH_PREFIXES = (
    "/admin/",
    "/static/",
    "/favicon.ico",
)
