from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from pricing.models import CommercialPrice, PriceAmount
from retail.selectors import (
    get_batch_for_retail_price,
    list_batches_for_retail_price,
)
from retail.tests.factories import (
    retail_batch_price_factory,
    retail_inventory_batch_factory,
    retail_product_factory,
    retail_product_price_factory,
)


@pytest.mark.django_db
def test_product_price_returns_eligible_batches():
    today = timezone.localdate()
    product = retail_product_factory()
    commercial_price = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        best_before=today + timedelta(days=30),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [batch]


@pytest.mark.django_db
def test_product_price_excludes_batch_with_own_retail_price():
    today = timezone.localdate()
    product = retail_product_factory()
    product_price = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    ordinary = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="ORDINARY",
        best_before=today + timedelta(days=30),
    )
    special = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="SPECIAL",
        best_before=today + timedelta(days=10),
    )
    retail_batch_price_factory(
        batch=special,
        enabled=True,
        price=Decimal("3.90"),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=product_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [ordinary]


@pytest.mark.django_db
def test_business_batch_price_does_not_remove_batch_from_retail_pool():
    today = timezone.localdate()
    product = retail_product_factory()
    retail_price = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
    )

    business_price = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    PriceAmount.objects.create(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("4.90"),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=retail_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [batch]


@pytest.mark.django_db
def test_batch_price_returns_exact_batch():
    today = timezone.localdate()
    commercial_price = retail_batch_price_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    assert (
        get_batch_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
        == commercial_price.batch
    )


@pytest.mark.django_db
def test_product_price_has_no_exact_batch():
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("6.90"),
    )

    assert get_batch_for_retail_price(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
    ) is None


@pytest.mark.django_db
def test_disabled_price_has_no_stock_pool():
    commercial_price = retail_product_price_factory(
        enabled=False,
        price=Decimal("6.90"),
    )
    retail_inventory_batch_factory(
        product=commercial_price.product,
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )
    ) == []


@pytest.mark.django_db
def test_requested_currency_is_required():
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("69.00"),
        currency=PriceAmount.Currency.SEK,
    )
    retail_inventory_batch_factory(
        product=commercial_price.product,
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )
    ) == []


@pytest.mark.django_db
def test_product_price_uses_fefo_order():
    today = timezone.localdate()
    product = retail_product_factory()
    commercial_price = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    later = retail_inventory_batch_factory(
        product=product,
        batch_id="LATER",
        best_before=today + timedelta(days=60),
    )
    earlier = retail_inventory_batch_factory(
        product=product,
        batch_id="EARLIER",
        best_before=today + timedelta(days=20),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [earlier, later]
