from __future__ import annotations

from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from inventory.models import InventoryBatch
from pricing.models import CommercialPrice
from pricing.selectors import (
    get_batch_price_amount,
    get_product_price_amount,
    list_orderable_batches_for_offer,
)


def list_batches_for_retail_price(
    *,
    commercial_price: CommercialPrice,
    currency: str,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return the stock pool represented by one retail CommercialPrice.

    Retail requires a matching, enabled PriceAmount before an offer is
    considered sellable at all - unlike business, which allows an unpriced
    standard offer. That check happens here, in retail; the pool mechanics
    themselves (which batches back the offer once it IS sellable) are the
    shared `pricing.list_orderable_batches_for_offer`.
    """

    today = today or timezone.localdate()

    if commercial_price.channel != CommercialPrice.Channel.RETAIL:
        return InventoryBatch.objects.none()

    if commercial_price.batch_id is not None:
        amount = get_batch_price_amount(
            batch=commercial_price.batch,
            channel=CommercialPrice.Channel.RETAIL,
            currency=currency,
        )
    else:
        amount = get_product_price_amount(
            product=commercial_price.product,
            channel=CommercialPrice.Channel.RETAIL,
            currency=currency,
        )

    if (
        amount is None
        or amount.commercial_price_id != commercial_price.pk
    ):
        return InventoryBatch.objects.none()

    return list_orderable_batches_for_offer(
        offer=commercial_price,
        currency=currency,
        today=today,
    )


def get_batch_for_retail_price(
    *,
    commercial_price: CommercialPrice,
    currency: str,
    today: date | None = None,
) -> InventoryBatch | None:
    """Return the exact batch for a batch-specific retail price."""

    if commercial_price.batch_id is None:
        return None

    return (
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=currency,
            today=today,
        )
        .select_related("product")
        .first()
    )
