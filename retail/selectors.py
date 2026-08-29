from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from inventory.expiry import (
    orderable_best_before_cutoff,
)
from inventory.models import InventoryBatch
from retail.models import (
    RetailBatchOffer,
    RetailProductOffer,
)
from retail.rules import (
    is_retail_product_sellable,
)


def list_batches_for_product_offer(
    *,
    offer: RetailProductOffer,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return physical batches eligible for a general retail product offer.

    Enabled batch-specific offers form separate commercial stock pools and are
    therefore excluded from the general product pool.
    """

    today = today or timezone.localdate()

    if not is_retail_product_sellable(
        offer,
    ):
        return InventoryBatch.objects.none()

    cutoff = orderable_best_before_cutoff(
        today=today,
    )

    return (
        InventoryBatch.objects
        .filter(
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


def list_batches_for_batch_offer(
    *,
    offer: RetailBatchOffer,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return the one physical batch eligible for a batch-specific offer.

    The QuerySet remains lazy so the reservation service can apply
    select_for_update() before trusting physical batch state.
    """

    today = today or timezone.localdate()

    if (
        not offer.enabled
        or offer.price is None
        or offer.price <= Decimal("0.00")
        or not offer.batch.product.active
    ):
        return InventoryBatch.objects.none()

    cutoff = orderable_best_before_cutoff(
        today=today,
    )

    return (
        InventoryBatch.objects
        .filter(
            pk=offer.batch_id,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gt=cutoff,
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

    Kept as a read convenience for callers that need the object directly.
    Reservation workflows should prefer list_batches_for_batch_offer() so the
    batch remains lockable as a lazy QuerySet.
    """

    return (
        list_batches_for_batch_offer(
            offer=offer,
            today=today,
        )
        .select_related("product")
        .first()
    )
