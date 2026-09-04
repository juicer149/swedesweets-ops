from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from pricing.models import CommercialPrice, PriceAmount
from pricing.tests.factories import (
    commercial_price_factory,
    price_amount_factory,
    pricing_batch_factory,
    pricing_product_factory,
)


@pytest.mark.django_db
def test_product_price_is_not_batch_specific():
    commercial_price = commercial_price_factory()

    assert commercial_price.batch_id is None
    assert not commercial_price.is_batch_specific


@pytest.mark.django_db
def test_batch_price_is_batch_specific():
    batch = pricing_batch_factory()

    commercial_price = commercial_price_factory(
        batch=batch,
    )

    assert commercial_price.product == batch.product
    assert commercial_price.batch == batch
    assert commercial_price.is_batch_specific


@pytest.mark.django_db
def test_batch_must_belong_to_commercial_price_product():
    product = pricing_product_factory(
        name="Product A",
    )
    other_product = pricing_product_factory(
        name="Product B",
    )
    batch = pricing_batch_factory(
        product=other_product,
    )

    commercial_price = CommercialPrice(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
    )

    with pytest.raises(
        ValidationError,
        match="Batch must belong to the same product",
    ):
        commercial_price.full_clean()


@pytest.mark.django_db
def test_product_can_have_separate_business_and_retail_prices():
    product = pricing_product_factory()

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )
    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert retail_price.product == business_price.product
    assert retail_price.channel != business_price.channel


@pytest.mark.django_db(transaction=True)
def test_product_can_have_only_one_product_wide_price_per_channel():
    product = pricing_product_factory()

    commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )

    with pytest.raises(IntegrityError):
        commercial_price_factory(
            product=product,
            channel=CommercialPrice.Channel.RETAIL,
        )


@pytest.mark.django_db
def test_batch_can_have_separate_business_and_retail_prices():
    batch = pricing_batch_factory()

    retail_price = commercial_price_factory(
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
    )
    business_price = commercial_price_factory(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert retail_price.batch == business_price.batch
    assert retail_price.channel != business_price.channel


@pytest.mark.django_db(transaction=True)
def test_batch_can_have_only_one_price_per_channel():
    batch = pricing_batch_factory()

    commercial_price_factory(
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
    )

    with pytest.raises(IntegrityError):
        commercial_price_factory(
            batch=batch,
            channel=CommercialPrice.Channel.RETAIL,
        )


@pytest.mark.django_db
def test_same_product_can_have_product_and_batch_price_in_same_channel():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )

    product_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )
    batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    assert product_price.batch_id is None
    assert batch_price.batch == batch


@pytest.mark.django_db
def test_reason_can_describe_short_dated_batch_pricing():
    batch = pricing_batch_factory()

    commercial_price = commercial_price_factory(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    assert commercial_price.reason == CommercialPrice.Reason.SHORT_DATED


@pytest.mark.django_db
def test_blank_reason_represents_ordinary_pricing():
    commercial_price = commercial_price_factory(
        reason="",
    )

    assert commercial_price.reason == ""


@pytest.mark.django_db
def test_one_commercial_price_can_have_eur_and_sek_amounts():
    commercial_price = commercial_price_factory(
        enabled=True,
    )

    eur = price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )
    sek = price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("99.00"),
    )

    assert list(
        commercial_price.amounts.order_by("currency")
    ) == [eur, sek]


@pytest.mark.django_db(transaction=True)
def test_commercial_price_can_have_only_one_amount_per_currency():
    commercial_price = commercial_price_factory()

    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
    )

    with pytest.raises(IntegrityError):
        price_amount_factory(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )


@pytest.mark.django_db(transaction=True)
def test_price_must_be_positive():
    commercial_price = commercial_price_factory()

    with pytest.raises(IntegrityError):
        price_amount_factory(
            commercial_price=commercial_price,
            price=Decimal("0.00"),
        )


@pytest.mark.django_db
def test_original_price_can_be_omitted_for_ordinary_price():
    amount = price_amount_factory(
        price=Decimal("9.00"),
    )

    assert amount.original_price is None
    assert not amount.is_discounted


@pytest.mark.django_db
def test_original_price_marks_discount_when_above_current_price():
    amount = price_amount_factory(
        price=Decimal("5.00"),
        original_price=Decimal("9.00"),
    )

    assert amount.is_discounted


@pytest.mark.django_db
def test_equal_original_price_is_not_discounted():
    amount = price_amount_factory(
        price=Decimal("9.00"),
        original_price=Decimal("9.00"),
    )

    assert not amount.is_discounted


@pytest.mark.django_db(transaction=True)
def test_original_price_cannot_be_below_current_price():
    commercial_price = commercial_price_factory()

    with pytest.raises(IntegrityError):
        price_amount_factory(
            commercial_price=commercial_price,
            price=Decimal("9.00"),
            original_price=Decimal("5.00"),
        )
