from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import get_product_commercial_price
from pricing.services import (
    create_commercial_price,
    ensure_standard_offer,
    remove_price_amount,
    set_commercial_price_enabled,
    set_price_amount,
)
from products.models import Product


@transaction.atomic
def update_product_standard_pricing(
    *,
    product: Product,
    business_eur: Decimal | None,
    business_sek: Decimal | None,
    business_enabled: bool,
    retail_eur: Decimal | None,
    retail_sek: Decimal | None,
    retail_enabled: bool,
) -> None:
    """Apply product-wide ordinary pricing configured from the ops product UI.

    BUSINESS: `business_enabled` is channel availability of the business
    standard offer. Amounts are optional.

    RETAIL: `retail_enabled` activates retail pricing, which requires at
    least one amount (validated by the form).
    """

    _update_channel_pricing(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=business_enabled,
        amounts={
            PriceAmount.Currency.EUR: business_eur,
            PriceAmount.Currency.SEK: business_sek,
        },
    )

    _update_channel_pricing(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=retail_enabled,
        amounts={
            PriceAmount.Currency.EUR: retail_eur,
            PriceAmount.Currency.SEK: retail_sek,
        },
    )


def _update_channel_pricing(
    *,
    product: Product,
    channel: str,
    enabled: bool,
    amounts: dict[str, Decimal | None],
) -> None:
    commercial_price = get_product_commercial_price(
        product=product,
        channel=channel,
    )

    if commercial_price is None:
        if channel == CommercialPrice.Channel.BUSINESS:
            # Every product should already have its business standard offer
            # (data migration + product creation hook); recreate it with the
            # correct semantics if it is somehow missing.
            commercial_price = ensure_standard_offer(
                product=product,
                channel=channel,
            )
        else:
            has_amount = any(
                amount is not None
                for amount in amounts.values()
            )

            if not has_amount and not enabled:
                return

            commercial_price = create_commercial_price(
                product=product,
                channel=channel,
            )

    for currency, amount in amounts.items():
        if amount is None:
            remove_price_amount(
                commercial_price=commercial_price,
                currency=currency,
            )
            continue

        set_price_amount(
            commercial_price=commercial_price,
            currency=currency,
            price=amount,
        )

    set_commercial_price_enabled(
        commercial_price=commercial_price,
        enabled=enabled,
    )
