from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from inventory.models import InventoryBatch
from inventory.tests.factories import batch_factory
from pricing.models import CommercialPrice, PriceAmount
from products.models import Product
from products.tests.factories import product_factory


def pricing_product_factory(**overrides) -> Product:
    defaults = {
        "brand": "SwedeSweets",
        "name": "Pricing Test Product",
    }

    return product_factory(**(defaults | overrides))


def pricing_batch_factory(
    *,
    product: Product | None = None,
    batch_id: str = "PRICE-001",
) -> InventoryBatch:
    today = timezone.localdate()
    product = product or pricing_product_factory()

    return batch_factory(
        product=product,
        today=today,
        batch_id=batch_id,
        quantity=10,
        best_before=today + timedelta(days=30),
        location="Pricing Shelf",
    )


def commercial_price_factory(
    *,
    product: Product | None = None,
    batch: InventoryBatch | None = None,
    channel: str = CommercialPrice.Channel.RETAIL,
    reason: str = "",
    enabled: bool = False,
) -> CommercialPrice:
    if product is None:
        product = batch.product if batch is not None else pricing_product_factory()

    return CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=channel,
        reason=reason,
        enabled=enabled,
    )


def price_amount_factory(
    *,
    commercial_price: CommercialPrice | None = None,
    currency: str = PriceAmount.Currency.EUR,
    price: Decimal = Decimal("10.00"),
    original_price: Decimal | None = None,
) -> PriceAmount:
    commercial_price = commercial_price or commercial_price_factory()

    return PriceAmount.objects.create(
        commercial_price=commercial_price,
        currency=currency,
        price=price,
        original_price=original_price,
    )

