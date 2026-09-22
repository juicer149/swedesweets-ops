from __future__ import annotations

from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from inventory.expiry import orderable_best_before_cutoff
from inventory.models import InventoryBatch
from pricing.models import CommercialPrice
from pricing.selectors import (
    get_batch_price_amount,
    get_product_price_amount,
)


def list_batches_for_retail_price(
    *,
    commercial_price: CommercialPrice,
    currency: str,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return the stock pool represented by one retail CommercialPrice.

    A product-wide price uses eligible ordinary batches, excluding batches
    that have their own enabled retail price in the requested currency.

    A batch-specific price uses only its exact physical batch.
    """

    today = today or timezone.localdate()

    if commercial_price.channel != CommercialPrice.Channel.RETAIL:
        return InventoryBatch.objects.none()

    cutoff = orderable_best_before_cutoff(
        today=today,
    )

    if commercial_price.batch_id is not None:
        amount = get_batch_price_amount(
            batch=commercial_price.batch,
            channel=CommercialPrice.Channel.RETAIL,
            currency=currency,
        )

        if (
            amount is None
            or amount.commercial_price_id != commercial_price.pk
            or not commercial_price.product.active
        ):
            return InventoryBatch.objects.none()

        return (
            InventoryBatch.objects
            .filter(
                pk=commercial_price.batch_id,
                status=InventoryBatch.Status.ACTIVE,
                quantity__gt=0,
                best_before__gt=cutoff,
            )
            .order_by(
                "best_before",
                "batch_id",
            )
        )

    amount = get_product_price_amount(
        product=commercial_price.product,
        channel=CommercialPrice.Channel.RETAIL,
        currency=currency,
    )

    if (
        amount is None
        or amount.commercial_price_id != commercial_price.pk
        or not commercial_price.product.active
    ):
        return InventoryBatch.objects.none()

    # NOTE: a single multi-condition .exclude() across the many-valued
    # `commercial_prices` relation does NOT require all conditions to match
    # the same related CommercialPrice row - Django ORs the per-row matches
    # per condition independently for exclude() on multi-valued relations.
    # A batch with a *disabled* RETAIL batch price and an unrelated *enabled*
    # BUSINESS batch price could therefore be wrongly excluded. Use an
    # explicit subquery (itself a .filter(), which DOES require all
    # conditions on the same row) instead.
    excluded_batch_ids = (
        CommercialPrice.objects
        .filter(
            channel=CommercialPrice.Channel.RETAIL,
            enabled=True,
            batch__isnull=False,
            amounts__currency=currency,
        )
        .values("batch_id")
    )

    return (
        InventoryBatch.objects
        .filter(
            product=commercial_price.product,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gt=cutoff,
        )
        .exclude(
            pk__in=excluded_batch_ids,
        )
        .order_by(
            "best_before",
            "batch_id",
        )
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
