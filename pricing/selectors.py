from __future__ import annotations

from collections.abc import Collection
from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from inventory.expiry import orderable_best_before_cutoff
from inventory.models import InventoryBatch
from inventory.selectors import list_orderable_batches_for_product
from pricing.models import CommercialPrice, PriceAmount
from products.models import Product


def _filter_channels(
    prices: QuerySet[CommercialPrice],
    *,
    channels: Collection[str] | None,
) -> QuerySet[CommercialPrice]:
    if channels is None:
        return prices

    return prices.filter(
        channel__in=channels,
    )


def get_product_commercial_price(
    *,
    product: Product,
    channel: str,
) -> CommercialPrice | None:
    """Return the product-wide pricing definition for one sales channel.

    Disabled pricing is deliberately included because ops needs to edit the
    configured definition, not only resolve currently sellable pricing.
    """

    return (
        CommercialPrice.objects
        .prefetch_related("amounts")
        .filter(
            product=product,
            batch__isnull=True,
            channel=channel,
        )
        .first()
    )

def get_batch_commercial_price(
    *,
    batch: InventoryBatch,
    channel: str,
) -> CommercialPrice | None:
    """Return the batch-specific pricing definition for one sales channel.

    Disabled pricing is deliberately included because ops needs to edit the
    configured definition, not only resolve currently sellable pricing.
    """

    return (
        CommercialPrice.objects
        .prefetch_related("amounts")
        .filter(
            batch=batch,
            channel=channel,
        )
        .first()
    )


def get_product_price_amount(
    *,
    product: Product,
    channel: str,
    currency: str,
) -> PriceAmount | None:
    """Return the enabled product-wide amount for one channel and currency."""

    return (
        PriceAmount.objects
        .select_related(
            "commercial_price",
            "commercial_price__product",
        )
        .filter(
            commercial_price__product=product,
            commercial_price__batch__isnull=True,
            commercial_price__channel=channel,
            commercial_price__enabled=True,
            currency=currency,
        )
        .first()
    )


def get_batch_price_amount(
    *,
    batch: InventoryBatch,
    channel: str,
    currency: str,
) -> PriceAmount | None:
    """Return the enabled amount configured for one exact batch."""

    return (
        PriceAmount.objects
        .select_related(
            "commercial_price",
            "commercial_price__product",
            "commercial_price__batch",
        )
        .filter(
            commercial_price__batch=batch,
            commercial_price__channel=channel,
            commercial_price__enabled=True,
            currency=currency,
        )
        .first()
    )


def resolve_price_amount(
    *,
    product: Product,
    channel: str,
    currency: str,
    batch: InventoryBatch | None = None,
) -> PriceAmount | None:
    """Resolve the applicable amount for one product scope.

    A batch-specific price has precedence over the product-wide price.
    Missing or disabled batch pricing falls back to product-wide pricing.

    The selector returns None when no enabled price exists in the requested
    channel and currency.
    """

    if batch is not None:
        if batch.product_id != product.pk:
            return None

        batch_amount = get_batch_price_amount(
            batch=batch,
            channel=channel,
            currency=currency,
        )

        if batch_amount is not None:
            return batch_amount

    return get_product_price_amount(
        product=product,
        channel=channel,
        currency=currency,
    )


def list_orderable_batches_for_offer(
    *,
    offer: CommercialPrice,
    currency: str,
    today: date | None = None,
) -> QuerySet[InventoryBatch]:
    """Return the stock pool one CommercialPrice offer can draw from.

    This is the mechanism shared by every channel: which physical batches
    back a given offer right now. It does not decide whether the offer
    itself is currently sellable in the requested currency (e.g. whether it
    has a PriceAmount) - callers that need that guarantee (retail) check it
    themselves before calling; callers that allow an unpriced standard offer
    (business) simply don't.

    A disabled offer, or an offer for an inactive product, has no pool.

    A batch-specific offer's pool is exactly its own batch.

    A product-wide offer's pool is the product's ordinary orderable batches,
    excluding any batch that has its own *enabled* same-channel offer priced
    in the requested currency - that batch is sold through its own offer
    instead, so its stock must not also be claimable through the product-wide
    one.
    """

    today = today or timezone.localdate()

    if not offer.enabled or not offer.product.active:
        return InventoryBatch.objects.none()

    if offer.batch_id is not None:
        cutoff = orderable_best_before_cutoff(today=today)

        return (
            InventoryBatch.objects
            .filter(
                pk=offer.batch_id,
                status=InventoryBatch.Status.ACTIVE,
                quantity__gt=0,
                best_before__gt=cutoff,
            )
            .select_related("product")
            .order_by("best_before", "batch_id")
        )

    return (
        list_orderable_batches_for_product(
            product=offer.product,
            today=today,
        )
        .exclude(
            commercial_prices__channel=offer.channel,
            commercial_prices__enabled=True,
            commercial_prices__amounts__currency=currency,
            commercial_prices__batch__isnull=False,
        )
    )


def list_commercial_prices(
    *,
    channels: Collection[str] | None = None,
    enabled_only: bool = False,
) -> QuerySet[CommercialPrice]:
    """List commercial pricing records across all products.

    By default all channels and enabled states are returned.

    `channels` narrows the result to the requested sales channels.
    Passing an empty collection deliberately returns an empty QuerySet.

    Amounts are prefetched because callers commonly need every configured
    currency while composing pricing or catalog read models.
    """

    prices = (
        CommercialPrice.objects
        .select_related(
            "product",
            "batch",
        )
        .prefetch_related(
            "amounts",
        )
        .order_by(
            "product_id",
            "channel",
            "batch_id",
            "id",
        )
    )

    prices = _filter_channels(
        prices,
        channels=channels,
    )

    if enabled_only:
        prices = prices.filter(
            enabled=True,
        )

    return prices


def list_commercial_prices_for_product(
    *,
    product: Product,
    channels: Collection[str] | None = None,
    enabled_only: bool = False,
) -> QuerySet[CommercialPrice]:
    """List commercial pricing records owned by one product.

    By default all channels and enabled states are returned.

    `channels` may contain one or more sales channels. Passing an empty
    collection deliberately returns an empty QuerySet.
    """

    prices = list_commercial_prices(
        channels=channels,
        enabled_only=enabled_only,
    ).filter(
        product=product,
    )

    return prices.order_by(
        "channel",
        "batch_id",
        "id",
    )
