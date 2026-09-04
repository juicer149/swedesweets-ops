from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from inventory.expiry import is_orderable_best_before
from inventory.models import InventoryBatch
from retail.models import (
    RetailBatchOffer,
    RetailPostalArea,
    RetailProductOffer,
)


MIN_RETAIL_LINE_QUANTITY = 1
MAX_RETAIL_LINE_QUANTITY = 20

MAX_RETAIL_ORDER_LINES = 20
MAX_RETAIL_ORDER_TOTAL = Decimal("1000.00")

RETAIL_CHECKOUT_WINDOW = timedelta(minutes=90)
RETAIL_PAYMENT_RESERVATION_WINDOW = timedelta(minutes=35)


def is_supported_retail_destination(
    *,
    country_code: str,
    postal_code: str,
    city: str,
) -> bool:
    """Return whether SwedeSweets currently delivers to this destination.

    Country, postal code and city must identify one enabled postal-area record.

    Street-address validation is intentionally outside the V1 scope.
    """

    country = country_code.strip().upper()
    postal = postal_code.strip()
    normalized_city = " ".join(city.strip().split())

    if not country or not postal or not normalized_city:
        return False

    return RetailPostalArea.objects.filter(
        country_code=country,
        postal_code=postal,
        city__iexact=normalized_city,
        enabled=True,
    ).exists()


def is_retail_product_sellable(
    offer: RetailProductOffer,
) -> bool:
    """Return whether a product is commercially enabled for retail.

    Physical stock is deliberately not evaluated here. Product offers describe
    general retail eligibility; inventory availability belongs to the stock and
    reservation layer.
    """

    return (
        offer.enabled
        and offer.price is not None
        and offer.price > Decimal("0.00")
        and offer.product.active
    )


def is_retail_batch_sellable(
    offer: RetailBatchOffer,
    *,
    today: date | None = None,
) -> bool:
    """Return whether one explicitly configured batch can be sold in retail.

    Operator intent is combined with current physical batch state.

    Reservation availability is deliberately not checked here.
    """

    today = today or timezone.localdate()
    batch = offer.batch

    return (
        offer.enabled
        and offer.price is not None
        and offer.price > Decimal("0.00")
        and batch.product.active
        and batch.status == InventoryBatch.Status.ACTIVE
        and batch.quantity > 0
        and is_orderable_best_before(
            best_before=batch.best_before,
            today=today,
        )
    )


def is_valid_retail_line_quantity(quantity: int) -> bool:
    return MIN_RETAIL_LINE_QUANTITY <= quantity <= MAX_RETAIL_LINE_QUANTITY


def is_valid_retail_order_total(total: Decimal) -> bool:
    return Decimal("0.00") < total <= MAX_RETAIL_ORDER_TOTAL
