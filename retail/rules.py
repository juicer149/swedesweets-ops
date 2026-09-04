from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from retail.models import RetailPostalArea


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
    """Return whether SwedeSweets currently delivers to this destination."""

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


def is_valid_retail_line_quantity(quantity: int) -> bool:
    return MIN_RETAIL_LINE_QUANTITY <= quantity <= MAX_RETAIL_LINE_QUANTITY


def is_valid_retail_order_total(total: Decimal) -> bool:
    return Decimal("0.00") < total <= MAX_RETAIL_ORDER_TOTAL
