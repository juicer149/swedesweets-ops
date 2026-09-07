from __future__ import annotations

import pytest

from business_portal.orders.views import (
    PortalOrderIntent,
)


def test_portal_order_intent_rejects_unknown_value():
    with pytest.raises(ValueError):
        PortalOrderIntent("not_a_real_intent")
