from __future__ import annotations

from decimal import Decimal

from orders.models import Order, OrderLine
from pricing.models import CommercialPrice
from products.models import Product


def order_line_factory(
    *,
    order: Order,
    product: Product,
    quantity: int = 1,
    commercial_offer: CommercialPrice | None = None,
    unit_price_snapshot: Decimal | None = None,
) -> OrderLine:
    """Create a valid current-schema order line.

    Tests concerned with commercial identity should pass `commercial_offer`
    explicitly. Tests concerned with unrelated order-line behavior may rely on
    this factory to resolve the required product-level offer identity.
    """

    if commercial_offer is None:
        commercial_offer, _created = CommercialPrice.objects.get_or_create(
            product=product,
            batch=None,
            channel=order.channel,
            defaults={
                "enabled": True,
            },
        )

    return OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
        unit_price_snapshot=unit_price_snapshot,
        commercial_offer=commercial_offer,
    )
