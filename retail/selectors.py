from __future__ import annotations

from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from inventory.expiry import orderable_best_before_cutoff
from inventory.models import InventoryBatch
from products.models import Product
from retail.models import RetailBatchOffer, RetailProductOffer
from retail.rules import (
    is_retail_batch_sellable,
    is_retail_product_sellable,
)


def list_batches_for_product_offer(
    *,
    offer: RetailProductOffer,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return physical batches available to a general product retail offer.

    The product offer owns the general commercial eligibility and price.

    Batch-specific enabled retail offers form separate commercial offers and
    are therefore excluded from the general product pool.

    Returned batches are ordered FEFO.
    """

    today = today or timezone.localdate()

    if not is_retail_product_sellable(offer):
        return InventoryBatch.objects.none()

    cutoff = orderable_best_before_cutoff(today=today)

    return (
        InventoryBatch.objects.filter(
            product=offer.product,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gt=cutoff,
        )
        .exclude(
            retail_offer__enabled=True,
        )
        .order_by(
            "best_before",
            "batch_id",
        )
    )


def get_batch_for_batch_offer(
    *,
    offer: RetailBatchOffer,
    today: date | None = None,
) -> InventoryBatch | None:
    """Return the physical batch for an active batch-specific retail offer.

    A batch offer represents its own commercial stock pool. It therefore never
    falls through to other batches of the same product.
    """

    today = today or timezone.localdate()

    if not is_retail_batch_sellable(
        offer,
        today=today,
    ):
        return None

    return offer.batch
