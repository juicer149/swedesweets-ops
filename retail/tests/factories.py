from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from inventory.models import InventoryBatch
from inventory.tests.factories import batch_factory
from pricing.models import CommercialPrice, PriceAmount
from products.models import Product
from products.tests.factories import product_factory
from retail.models import RetailPostalArea


@dataclass(frozen=True)
class RetailBuyerFactoryData:
    first_name: str = "Marie"
    last_name: str = "Dupont"
    email: str = "marie@example.com"
    phone_number: str = "+33612345678"

    country: str = "FR"
    postal_code: str = "74000"
    city: str = "Annecy"
    address_line: str = "10 Rue de Test"

    def as_dict(self, **overrides: str) -> dict[str, str]:
        return asdict(self) | overrides


def retail_buyer_data(**overrides: str) -> dict[str, str]:
    return RetailBuyerFactoryData().as_dict(**overrides)


def retail_postal_area_factory(
    *,
    country_code: str = "FR",
    postal_code: str = "74000",
    city: str = "Annecy",
    enabled: bool = True,
) -> RetailPostalArea:
    return RetailPostalArea.objects.create(
        country_code=country_code,
        postal_code=postal_code,
        city=city,
        enabled=enabled,
    )


def retail_product_factory(**overrides) -> Product:
    defaults = {
        "brand": "SwedeSweets",
        "name": "Retail Test Product",
    }

    return product_factory(**(defaults | overrides))


def retail_inventory_batch_factory(
    *,
    product: Product | None = None,
    today: date | None = None,
    batch_id: str = "RET-001",
    quantity: int = 10,
    best_before: date | None = None,
    location: str = "Retail Shelf",
) -> InventoryBatch:
    today = today or timezone.localdate()
    product = product or retail_product_factory()

    return batch_factory(
        product=product,
        today=today,
        batch_id=batch_id,
        quantity=quantity,
        best_before=best_before or today + timedelta(days=30),
        location=location,
    )


def retail_product_price_factory(
    *,
    product: Product | None = None,
    enabled: bool = False,
    price: Decimal | None = None,
    currency: str = PriceAmount.Currency.EUR,
    original_price: Decimal | None = None,
    reason: str = "",
) -> CommercialPrice:
    product = product or retail_product_factory()

    commercial_price = CommercialPrice.objects.create(
        product=product,
        batch=None,
        channel=CommercialPrice.Channel.RETAIL,
        reason=reason,
        enabled=enabled,
    )

    if price is not None:
        PriceAmount.objects.create(
            commercial_price=commercial_price,
            currency=currency,
            price=price,
            original_price=original_price,
        )

    return commercial_price


def retail_batch_price_factory(
    *,
    batch: InventoryBatch | None = None,
    enabled: bool = False,
    price: Decimal | None = None,
    currency: str = PriceAmount.Currency.EUR,
    original_price: Decimal | None = None,
    reason: str = CommercialPrice.Reason.SHORT_DATED,
) -> CommercialPrice:
    batch = batch or retail_inventory_batch_factory()

    commercial_price = CommercialPrice.objects.create(
        product=batch.product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=reason,
        enabled=enabled,
    )

    if price is not None:
        PriceAmount.objects.create(
            commercial_price=commercial_price,
            currency=currency,
            price=price,
            original_price=original_price,
        )

    return commercial_price
