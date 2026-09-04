from __future__ import annotations

from decimal import Decimal

import pytest

from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import (
    get_batch_price_amount,
    get_product_price_amount,
    list_commercial_prices,
    list_commercial_prices_for_product,
    resolve_price_amount,
)
from pricing.tests.factories import (
    commercial_price_factory,
    price_amount_factory,
    pricing_batch_factory,
    pricing_product_factory,
)


@pytest.mark.django_db
def test_get_product_price_amount_returns_enabled_requested_currency():
    product = pricing_product_factory()
    commercial_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    eur = price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("99.00"),
    )

    resolved = get_product_price_amount(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    )

    assert resolved == eur


@pytest.mark.django_db
def test_get_product_price_amount_ignores_disabled_pricing():
    product = pricing_product_factory()
    commercial_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=False,
    )
    price_amount_factory(
        commercial_price=commercial_price,
    )

    assert get_product_price_amount(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    ) is None


@pytest.mark.django_db
def test_get_product_price_amount_requires_requested_currency():
    product = pricing_product_factory()
    commercial_price = commercial_price_factory(
        product=product,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
    )

    assert get_product_price_amount(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.SEK,
    ) is None


@pytest.mark.django_db
def test_get_batch_price_amount_returns_exact_batch_pricing():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )
    commercial_price = commercial_price_factory(
        product=product,
        batch=batch,
        enabled=True,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )
    amount = price_amount_factory(
        commercial_price=commercial_price,
        price=Decimal("5.00"),
        original_price=Decimal("9.00"),
    )

    resolved = get_batch_price_amount(
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    )

    assert resolved == amount
    assert resolved.commercial_price.reason == CommercialPrice.Reason.SHORT_DATED


@pytest.mark.django_db
def test_resolve_price_amount_prefers_batch_specific_price():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )

    product_price = commercial_price_factory(
        product=product,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=product_price,
        price=Decimal("9.00"),
    )

    batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        enabled=True,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )
    batch_amount = price_amount_factory(
        commercial_price=batch_price,
        price=Decimal("5.00"),
        original_price=Decimal("9.00"),
    )

    resolved = resolve_price_amount(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    )

    assert resolved == batch_amount


@pytest.mark.django_db
def test_resolve_price_amount_falls_back_to_product_price():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )

    product_price = commercial_price_factory(
        product=product,
        enabled=True,
    )
    product_amount = price_amount_factory(
        commercial_price=product_price,
        price=Decimal("9.00"),
    )

    resolved = resolve_price_amount(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    )

    assert resolved == product_amount


@pytest.mark.django_db
def test_resolve_price_amount_falls_back_when_batch_price_is_disabled():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )

    product_price = commercial_price_factory(
        product=product,
        enabled=True,
    )
    product_amount = price_amount_factory(
        commercial_price=product_price,
        price=Decimal("9.00"),
    )

    batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        enabled=False,
    )
    price_amount_factory(
        commercial_price=batch_price,
        price=Decimal("5.00"),
    )

    resolved = resolve_price_amount(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    )

    assert resolved == product_amount


@pytest.mark.django_db
def test_resolve_price_amount_falls_back_when_batch_currency_is_missing():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )

    product_price = commercial_price_factory(
        product=product,
        enabled=True,
    )
    product_amount = price_amount_factory(
        commercial_price=product_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )

    batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=batch_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("55.00"),
    )

    resolved = resolve_price_amount(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    )

    assert resolved == product_amount


@pytest.mark.django_db
def test_resolve_price_amount_rejects_mismatched_batch_by_returning_none():
    product = pricing_product_factory(
        name="Product A",
    )
    other_product = pricing_product_factory(
        name="Product B",
    )
    batch = pricing_batch_factory(
        product=other_product,
    )

    product_price = commercial_price_factory(
        product=product,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=product_price,
    )

    assert resolve_price_amount(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    ) is None


@pytest.mark.django_db
def test_channel_is_part_of_price_resolution():
    product = pricing_product_factory()

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    retail_amount = price_amount_factory(
        commercial_price=retail_price,
        price=Decimal("9.00"),
    )

    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    business_amount = price_amount_factory(
        commercial_price=business_price,
        price=Decimal("7.00"),
    )

    assert resolve_price_amount(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        currency=PriceAmount.Currency.EUR,
    ) == retail_amount

    assert resolve_price_amount(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        currency=PriceAmount.Currency.EUR,
    ) == business_amount


@pytest.mark.django_db
def test_list_commercial_prices_returns_all_products_and_channels_by_default():
    product_a = pricing_product_factory(
        name="Product A",
    )
    product_b = pricing_product_factory(
        name="Product B",
    )

    retail_a = commercial_price_factory(
        product=product_a,
        channel=CommercialPrice.Channel.RETAIL,
    )
    business_a = commercial_price_factory(
        product=product_a,
        channel=CommercialPrice.Channel.BUSINESS,
    )
    retail_b = commercial_price_factory(
        product=product_b,
        channel=CommercialPrice.Channel.RETAIL,
    )

    prices = list(
        list_commercial_prices()
    )

    assert set(prices) == {
        retail_a,
        business_a,
        retail_b,
    }


@pytest.mark.django_db
def test_list_commercial_prices_can_filter_to_retail():
    product = pricing_product_factory()

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )
    commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    prices = list(
        list_commercial_prices(
            channels={
                CommercialPrice.Channel.RETAIL,
            },
        )
    )

    assert prices == [
        retail_price,
    ]


@pytest.mark.django_db
def test_list_commercial_prices_can_include_multiple_channels():
    product = pricing_product_factory()

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )
    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    prices = list(
        list_commercial_prices(
            channels={
                CommercialPrice.Channel.RETAIL,
                CommercialPrice.Channel.BUSINESS,
            },
        )
    )

    assert set(prices) == {
        retail_price,
        business_price,
    }


@pytest.mark.django_db
def test_list_commercial_prices_empty_channels_returns_empty_queryset():
    commercial_price_factory()

    assert list(
        list_commercial_prices(
            channels=set(),
        )
    ) == []


@pytest.mark.django_db
def test_list_commercial_prices_can_return_enabled_only():
    product = pricing_product_factory()

    enabled_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
    )

    prices = list(
        list_commercial_prices(
            enabled_only=True,
        )
    )

    assert prices == [
        enabled_price,
    ]


@pytest.mark.django_db
def test_list_commercial_prices_prefetches_amounts_for_composition(
    django_assert_num_queries,
):
    product = pricing_product_factory()

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )
    price_amount_factory(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("99.00"),
    )

    with django_assert_num_queries(2):
        prices = list(
            list_commercial_prices()
        )
        amounts = [
            list(price.amounts.all())
            for price in prices
        ]

    assert len(amounts[0]) == 2


@pytest.mark.django_db
def test_list_commercial_prices_for_product_returns_all_channels_by_default():
    product = pricing_product_factory()
    other_product = pricing_product_factory(
        name="Other Product",
    )

    retail_product = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )
    retail_batch = commercial_price_factory(
        product=product,
        batch=pricing_batch_factory(
            product=product,
        ),
        channel=CommercialPrice.Channel.RETAIL,
    )
    business_product = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )
    commercial_price_factory(
        product=other_product,
        channel=CommercialPrice.Channel.RETAIL,
    )

    prices = list(
        list_commercial_prices_for_product(
            product=product,
        )
    )

    assert set(prices) == {
        retail_product,
        retail_batch,
        business_product,
    }


@pytest.mark.django_db
def test_list_commercial_prices_for_product_can_filter_channels():
    product = pricing_product_factory()

    retail_product = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )
    retail_batch = commercial_price_factory(
        product=product,
        batch=pricing_batch_factory(
            product=product,
        ),
        channel=CommercialPrice.Channel.RETAIL,
    )
    commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    prices = list(
        list_commercial_prices_for_product(
            product=product,
            channels={
                CommercialPrice.Channel.RETAIL,
            },
        )
    )

    assert prices == [
        retail_product,
        retail_batch,
    ]


@pytest.mark.django_db
def test_list_commercial_prices_for_product_can_return_enabled_only():
    product = pricing_product_factory()

    enabled_retail = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
    )

    prices = list(
        list_commercial_prices_for_product(
            product=product,
            enabled_only=True,
        )
    )

    assert prices == [
        enabled_retail,
    ]
