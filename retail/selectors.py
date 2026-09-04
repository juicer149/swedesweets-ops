from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from inventory.expiry import (
    orderable_best_before_cutoff,
)
from inventory.models import InventoryBatch
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import (
    get_batch_price_amount,
    get_product_price_amount,
)
from retail.models import (
    RetailBatchOffer,
    RetailProductOffer,
)
from retail.rules import (
    is_retail_product_sellable,
)


def list_batches_for_retail_price(
    *,
    commercial_price: CommercialPrice,
    currency: str,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return the stock pool owned by one retail CommercialPrice.

    Product-wide pricing uses the ordinary eligible stock pool and excludes
    batches that have their own enabled retail price in the requested currency.

    Batch-specific pricing uses only the configured physical batch.

    The returned QuerySet remains lazy so reservation code may still apply
    select_for_update() before trusting physical stock state.
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

    return (
        InventoryBatch.objects
        .filter(
            product=commercial_price.product,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gt=cutoff,
        )
        .exclude(
            commercial_prices__channel=CommercialPrice.Channel.RETAIL,
            commercial_prices__enabled=True,
            commercial_prices__amounts__currency=currency,
            commercial_prices__batch__isnull=False,
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
    """Return the exact batch represented by a batch-specific retail price.

    Product-wide prices deliberately return None because they represent a pool,
    not one physical batch.
    """

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


def list_batches_for_product_offer(
    *,
    offer: RetailProductOffer,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return physical batches eligible for a legacy retail product offer.

    Kept temporarily while cart/order provenance is migrated to pricing.
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
    """Return the batch eligible for a legacy retail batch offer.

    Kept temporarily while cart/order provenance is migrated to pricing.
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
    """Return the batch for a legacy retail batch offer."""

    return (
        list_batches_for_batch_offer(
            offer=offer,
            today=today,
        )
        .select_related("product")
        .first()
    )
