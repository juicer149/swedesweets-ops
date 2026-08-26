from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from inventory.models import InventoryBatch
from retail.models import RetailBatchOffer, RetailPostalArea


MIN_RETAIL_LINE_QUANTITY = 1
MAX_RETAIL_LINE_QUANTITY = 20

MAX_RETAIL_ORDER_LINES = 20
MAX_RETAIL_ORDER_TOTAL = Decimal("1000.00")

RETAIL_PAYMENT_WINDOW = timedelta(minutes=10)


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


def is_retail_batch_sellable(
    offer: RetailBatchOffer,
    *,
    today: date | None = None,
) -> bool:
    """Return whether an explicitly configured batch can be sold in retail.

    `offer.enabled` expresses operator intent.

    Physical eligibility remains derived from the inventory batch:
    - the batch must be active,
    - physical stock must remain,
    - best-before must still be in the future.

    Reservation availability is deliberately not checked here. That belongs to
    the reservation/use-case layer.
    """

    today = today or timezone.localdate()
    batch = offer.batch

    return (
        offer.enabled
        and offer.price is not None
        and offer.price > Decimal("0.00")
        and batch.status == InventoryBatch.Status.ACTIVE
        and batch.quantity > 0
        and batch.best_before > today
    )


def is_valid_retail_line_quantity(quantity: int) -> bool:
    return MIN_RETAIL_LINE_QUANTITY <= quantity <= MAX_RETAIL_LINE_QUANTITY


def is_valid_retail_order_total(total: Decimal) -> bool:
    return Decimal("0.00") < total <= MAX_RETAIL_ORDER_TOTAL
