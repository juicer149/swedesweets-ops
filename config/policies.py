"""
Global route access policy composition.

Each HTTP-facing app declares the access policy for the views it owns in its
own access.py module. This module composes those declarations into the policy
maps enforced by ViewCapabilityMiddleware.

Views are denied by default unless listed here or marked auth-exempt.
"""

from __future__ import annotations

from accounts.access import (
    AUTH_EXEMPT_VIEWS as ACCOUNT_AUTH_EXEMPT_VIEWS,
)
from accounts.access import (
    VIEW_CAPABILITIES as ACCOUNT_VIEW_CAPABILITIES,
)
from business_portal.access import (
    VIEW_CAPABILITIES as BUSINESS_PORTAL_VIEW_CAPABILITIES,
)
from ops_portal.customers.access import (
    VIEW_CAPABILITIES as OPS_CUSTOMER_VIEW_CAPABILITIES,
)
from inventory.access import (
    VIEW_CAPABILITIES as INVENTORY_VIEW_CAPABILITIES,
)
from ops_portal.access import (
    VIEW_CAPABILITIES as OPS_PORTAL_VIEW_CAPABILITIES,
)
from ops_portal.accounts.access import (
    VIEW_CAPABILITIES as OPS_ACCOUNT_VIEW_CAPABILITIES,
)
from orders.access import (
    VIEW_CAPABILITIES as ORDER_VIEW_CAPABILITIES,
)
from payments.access import (
    AUTH_EXEMPT_VIEWS as PAYMENT_AUTH_EXEMPT_VIEWS,
)
from payments.access import (
    VIEW_CAPABILITIES as PAYMENT_VIEW_CAPABILITIES,
)
from ops_portal.products.access import (
    VIEW_CAPABILITIES as OPS_PRODUCT_VIEW_CAPABILITIES,
)
from storefront.access import (
    AUTH_EXEMPT_VIEWS as STOREFRONT_AUTH_EXEMPT_VIEWS,
)
from storefront.access import (
    VIEW_CAPABILITIES as STOREFRONT_VIEW_CAPABILITIES,
)


AUTH_EXEMPT_VIEWS = frozenset(
    {
        *ACCOUNT_AUTH_EXEMPT_VIEWS,
        *PAYMENT_AUTH_EXEMPT_VIEWS,
        *STOREFRONT_AUTH_EXEMPT_VIEWS,
    }
)


VIEW_CAPABILITIES = {
    **OPS_PORTAL_VIEW_CAPABILITIES,
    **OPS_ACCOUNT_VIEW_CAPABILITIES,
    **ACCOUNT_VIEW_CAPABILITIES,
    **ORDER_VIEW_CAPABILITIES,
    **INVENTORY_VIEW_CAPABILITIES,
    **OPS_PRODUCT_VIEW_CAPABILITIES,
    **OPS_CUSTOMER_VIEW_CAPABILITIES,
    **BUSINESS_PORTAL_VIEW_CAPABILITIES,
    **PAYMENT_VIEW_CAPABILITIES,
    **STOREFRONT_VIEW_CAPABILITIES,
}


EXEMPT_PATH_PREFIXES = (
    "/admin/",
    "/static/",
    "/favicon.ico",
)
