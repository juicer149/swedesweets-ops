from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from inventory.models import InventoryBatch
from pricing.errors import InvalidCommercialPrice
from pricing.models import CommercialPrice, PriceAmount
from products.models import Product


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


def _validate_amounts(
    *,
    price: Decimal,
    original_price: Decimal | None,
) -> None:
    if price <= Decimal("0.00"):
        raise InvalidCommercialPrice(
            "price must be greater than zero"
        )

    if original_price is None:
        return

    if original_price <= Decimal("0.00"):
        raise InvalidCommercialPrice(
            "original price must be greater than zero"
        )

    if original_price < price:
        raise InvalidCommercialPrice(
            "original price cannot be below current price"
        )


@transaction.atomic
def create_commercial_price(
    *,
    product: Product,
    channel: str,
    batch: InventoryBatch | None = None,
    reason: str = "",
) -> CommercialPrice:
    """Create disabled commercial pricing for one product scope."""

    existing_prices = CommercialPrice.objects.filter(
        channel=channel,
    )

    if batch is None:
        duplicate_exists = existing_prices.filter(
            product=product,
            batch__isnull=True,
        ).exists()
    else:
        duplicate_exists = existing_prices.filter(
            batch=batch,
        ).exists()

    if duplicate_exists:
        raise InvalidCommercialPrice(
            "commercial price already exists for this scope and channel"
        )

    commercial_price = CommercialPrice(
        product=product,
        batch=batch,
        channel=channel,
        reason=reason,
        enabled=False,
    )

    try:
        commercial_price.full_clean()
        commercial_price.save()
    except ValidationError as exc:
        raise InvalidCommercialPrice(
            "invalid commercial price configuration"
        ) from exc
    except IntegrityError as exc:
        raise InvalidCommercialPrice(
            "commercial price already exists for this scope and channel"
        ) from exc

    return commercial_price


@transaction.atomic
def set_price_amount(
    *,
    commercial_price: CommercialPrice,
    currency: str,
    price: Decimal | int | float | str,
    original_price: Decimal | int | float | str | None = None,
) -> PriceAmount:
    """Create or replace one currency amount on a commercial price."""

    locked_price = (
        CommercialPrice.objects
        .select_for_update()
        .get(pk=commercial_price.pk)
    )

    normalized_price = _to_decimal(price)
    normalized_original = (
        None
        if original_price is None
        else _to_decimal(original_price)
    )

    _validate_amounts(
        price=normalized_price,
        original_price=normalized_original,
    )

    amount, _ = PriceAmount.objects.update_or_create(
        commercial_price=locked_price,
        currency=currency,
        defaults={
            "price": normalized_price,
            "original_price": normalized_original,
        },
    )

    try:
        amount.full_clean()
    except ValidationError as exc:
        raise InvalidCommercialPrice(
            "invalid price amount"
        ) from exc

    return amount


@transaction.atomic
def set_commercial_price_reason(
    *,
    commercial_price: CommercialPrice,
    reason: str,
) -> CommercialPrice:
    """Update why the current pricing differs from ordinary pricing."""

    commercial_price = (
        CommercialPrice.objects
        .select_for_update()
        .get(pk=commercial_price.pk)
    )

    commercial_price.reason = reason

    try:
        commercial_price.full_clean()
    except ValidationError as exc:
        raise InvalidCommercialPrice(
            "invalid commercial price reason"
        ) from exc

    commercial_price.save(
        update_fields=[
            "reason",
            "updated_at",
        ],
    )

    return commercial_price


@transaction.atomic
def set_commercial_price_enabled(
    *,
    commercial_price: CommercialPrice,
    enabled: bool,
) -> CommercialPrice:
    """Enable or disable commercial pricing.

    An enabled commercial price must expose at least one currency amount.
    """

    commercial_price = (
        CommercialPrice.objects
        .select_for_update()
        .get(pk=commercial_price.pk)
    )

    if enabled and not commercial_price.amounts.exists():
        raise InvalidCommercialPrice(
            "commercial price requires at least one amount before enabling"
        )

    commercial_price.enabled = enabled
    commercial_price.save(
        update_fields=[
            "enabled",
            "updated_at",
        ],
    )

    return commercial_price

