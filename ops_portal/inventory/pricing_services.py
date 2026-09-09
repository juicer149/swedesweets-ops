from __future__ import annotations

from decimal import Decimal

from inventory.models import InventoryBatch
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import (
    get_batch_commercial_price,
)
from pricing.services import (
    create_commercial_price,
    remove_price_amount,
    set_commercial_price_enabled,
    set_commercial_price_reason,
    set_price_amount,
)


def update_batch_special_pricing(
    *,
    batch: InventoryBatch,
    reason: str,
    business_eur: Decimal | None,
    business_sek: Decimal | None,
    business_enabled: bool,
    retail_eur: Decimal | None,
    retail_sek: Decimal | None,
    retail_enabled: bool,
) -> None:
    _update_channel_pricing(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=reason,
        eur=business_eur,
        sek=business_sek,
        enabled=business_enabled,
    )

    _update_channel_pricing(
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=reason,
        eur=retail_eur,
        sek=retail_sek,
        enabled=retail_enabled,
    )


def _update_channel_pricing(
    *,
    batch: InventoryBatch,
    channel: str,
    reason: str,
    eur: Decimal | None,
    sek: Decimal | None,
    enabled: bool,
) -> None:
    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=channel,
    )

    has_amount = (
        eur is not None
        or sek is not None
    )

    if (
        commercial_price is None
        and not has_amount
        and not enabled
    ):
        return

    if commercial_price is None:
        commercial_price = create_commercial_price(
            product=batch.product,
            batch=batch,
            channel=channel,
            reason=reason,
        )
    else:
        set_commercial_price_reason(
            commercial_price=commercial_price,
            reason=reason,
        )

    _set_or_remove_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        amount=eur,
    )
    _set_or_remove_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.SEK,
        amount=sek,
    )

    set_commercial_price_enabled(
        commercial_price=commercial_price,
        enabled=enabled,
    )


def _set_or_remove_amount(
    *,
    commercial_price: CommercialPrice,
    currency: str,
    amount: Decimal | None,
) -> None:
    if amount is None:
        remove_price_amount(
            commercial_price=commercial_price,
            currency=currency,
        )
        return

    set_price_amount(
        commercial_price=commercial_price,
        currency=currency,
        price=amount,
    )
