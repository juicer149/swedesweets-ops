from __future__ import annotations

from pricing.models import CommercialPrice
from pricing.tests.factories import commercial_price_factory
from products.models import Product


def standard_business_offer_factory(
    *,
    product: Product,
    enabled: bool = True,
) -> CommercialPrice:
    """Create the persistent standard BUSINESS offer for one product."""

    return commercial_price_factory(
        product=product,
        batch=None,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=enabled,
    )
