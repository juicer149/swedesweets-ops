from __future__ import annotations

from decimal import Decimal

import pytest

from ops_portal.products.pricing_services import (
    update_product_standard_pricing,
)
from pricing.models import CommercialPrice, PriceAmount
from pricing.tests.factories import (
    commercial_price_factory,
    price_amount_factory,
    pricing_product_factory,
)


@pytest.mark.django_db
def test_update_product_standard_pricing_does_nothing_when_empty():
    product = pricing_product_factory()

    update_product_standard_pricing(
        product=product,
        business_eur=None,
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    assert CommercialPrice.objects.filter(
        product=product,
    ).count() == 0


@pytest.mark.django_db
def test_update_product_standard_pricing_creates_business_price():
    product = pricing_product_factory()

    update_product_standard_pricing(
        product=product,
        business_eur=Decimal("7.00"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = CommercialPrice.objects.get(
        product=product,
        batch__isnull=True,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert commercial_price.enabled is True
    assert commercial_price.reason == ""

    amount = commercial_price.amounts.get(
        currency=PriceAmount.Currency.EUR,
    )

    assert amount.price == Decimal("7.00")
    assert amount.original_price is None


@pytest.mark.django_db
def test_update_product_standard_pricing_creates_both_channels():
    product = pricing_product_factory()

    update_product_standard_pricing(
        product=product,
        business_eur=Decimal("7.00"),
        business_sek=Decimal("79.00"),
        business_enabled=True,
        retail_eur=Decimal("9.00"),
        retail_sek=Decimal("99.00"),
        retail_enabled=True,
    )

    business_price = CommercialPrice.objects.get(
        product=product,
        batch__isnull=True,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    retail_price = CommercialPrice.objects.get(
        product=product,
        batch__isnull=True,
        channel=CommercialPrice.Channel.RETAIL,
    )

    assert business_price.enabled is True
    assert retail_price.enabled is True

    assert {
        amount.currency: amount.price
        for amount in business_price.amounts.all()
    } == {
        PriceAmount.Currency.EUR: Decimal("7.00"),
        PriceAmount.Currency.SEK: Decimal("79.00"),
    }

    assert {
        amount.currency: amount.price
        for amount in retail_price.amounts.all()
    } == {
        PriceAmount.Currency.EUR: Decimal("9.00"),
        PriceAmount.Currency.SEK: Decimal("99.00"),
    }


@pytest.mark.django_db
def test_update_product_standard_pricing_can_store_disabled_price():
    product = pricing_product_factory()

    update_product_standard_pricing(
        product=product,
        business_eur=Decimal("7.00"),
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = CommercialPrice.objects.get(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        batch__isnull=True,
    )

    assert commercial_price.enabled is False
    assert (
        commercial_price.amounts.get(
            currency=PriceAmount.Currency.EUR,
        ).price
        == Decimal("7.00")
    )


@pytest.mark.django_db
def test_update_product_standard_pricing_updates_existing_amount():
    product = pricing_product_factory()

    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    amount = price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("7.00"),
    )

    update_product_standard_pricing(
        product=product,
        business_eur=Decimal("8.50"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    amount.refresh_from_db()

    assert amount.price == Decimal("8.50")
    assert CommercialPrice.objects.filter(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        batch__isnull=True,
    ).count() == 1


@pytest.mark.django_db
def test_update_product_standard_pricing_removes_cleared_currency():
    product = pricing_product_factory()

    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("7.00"),
    )
    sek = price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("79.00"),
    )

    update_product_standard_pricing(
        product=product,
        business_eur=None,
        business_sek=Decimal("79.00"),
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    assert not business_price.amounts.filter(
        currency=PriceAmount.Currency.EUR,
    ).exists()

    sek.refresh_from_db()
    assert sek.price == Decimal("79.00")


@pytest.mark.django_db
def test_update_product_standard_pricing_can_disable_existing_price():
    product = pricing_product_factory()

    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("7.00"),
    )

    update_product_standard_pricing(
        product=product,
        business_eur=Decimal("7.00"),
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    business_price.refresh_from_db()

    assert business_price.enabled is False


@pytest.mark.django_db
def test_update_product_standard_pricing_can_clear_all_amounts():
    product = pricing_product_factory()

    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
    )
    price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("7.00"),
    )
    price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("79.00"),
    )

    update_product_standard_pricing(
        product=product,
        business_eur=None,
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    business_price.refresh_from_db()

    assert business_price.enabled is False
    assert business_price.amounts.count() == 0


@pytest.mark.django_db
def test_update_product_standard_pricing_does_not_touch_batch_pricing():
    product = pricing_product_factory()

    from pricing.tests.factories import (
        pricing_batch_factory,
    )

    batch = pricing_batch_factory(
        product=product,
    )

    batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=CommercialPrice.Reason.SHORT_DATED,
        enabled=True,
    )
    batch_amount = price_amount_factory(
        commercial_price=batch_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("5.00"),
        original_price=Decimal("9.00"),
    )

    update_product_standard_pricing(
        product=product,
        business_eur=None,
        business_sek=None,
        business_enabled=False,
        retail_eur=Decimal("9.00"),
        retail_sek=None,
        retail_enabled=True,
    )

    batch_price.refresh_from_db()
    batch_amount.refresh_from_db()

    assert batch_price.enabled is True
    assert (
        batch_price.reason
        == CommercialPrice.Reason.SHORT_DATED
    )
    assert batch_amount.price == Decimal("5.00")
    assert batch_amount.original_price == Decimal("9.00")
