from decimal import Decimal

import pytest

from pricing.errors import InvalidCommercialPrice
from pricing.models import CommercialPrice, PriceAmount
from pricing.services import (
    create_commercial_price,
    set_commercial_price_enabled,
    set_commercial_price_reason,
    set_price_amount,
)
from pricing.tests.factories import (
    commercial_price_factory,
    pricing_batch_factory,
    pricing_product_factory,
)


@pytest.mark.django_db
def test_create_commercial_price_creates_disabled_product_price():
    product = pricing_product_factory()

    commercial_price = create_commercial_price(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )

    assert commercial_price.product == product
    assert commercial_price.batch_id is None
    assert commercial_price.channel == CommercialPrice.Channel.RETAIL
    assert commercial_price.reason == ""
    assert not commercial_price.enabled


@pytest.mark.django_db
def test_create_commercial_price_can_target_exact_batch():
    product = pricing_product_factory()
    batch = pricing_batch_factory(
        product=product,
    )

    commercial_price = create_commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    assert commercial_price.product == product
    assert commercial_price.batch == batch
    assert commercial_price.reason == CommercialPrice.Reason.SHORT_DATED


@pytest.mark.django_db
def test_create_commercial_price_rejects_batch_from_other_product():
    product = pricing_product_factory(
        name="Product A",
    )
    other_product = pricing_product_factory(
        name="Product B",
    )
    batch = pricing_batch_factory(
        product=other_product,
    )

    with pytest.raises(
        InvalidCommercialPrice,
        match="invalid commercial price configuration",
    ):
        create_commercial_price(
            product=product,
            batch=batch,
            channel=CommercialPrice.Channel.RETAIL,
        )


@pytest.mark.django_db
def test_create_commercial_price_rejects_duplicate_scope_and_channel():
    product = pricing_product_factory()

    create_commercial_price(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
    )

    with pytest.raises(
        InvalidCommercialPrice,
        match="already exists",
    ):
        create_commercial_price(
            product=product,
            channel=CommercialPrice.Channel.RETAIL,
        )


@pytest.mark.django_db
def test_set_price_amount_creates_currency_amount():
    commercial_price = commercial_price_factory()

    amount = set_price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price="9.00",
    )

    assert amount.currency == PriceAmount.Currency.EUR
    assert amount.price == Decimal("9.00")
    assert amount.original_price is None


@pytest.mark.django_db
def test_set_price_amount_replaces_existing_currency_amount():
    commercial_price = commercial_price_factory()

    first = set_price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price="9.00",
    )

    second = set_price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price="5.00",
        original_price="9.00",
    )

    assert second.pk == first.pk
    assert second.price == Decimal("5.00")
    assert second.original_price == Decimal("9.00")
    assert commercial_price.amounts.count() == 1


@pytest.mark.django_db
def test_set_price_amount_allows_multiple_currencies():
    commercial_price = commercial_price_factory()

    eur = set_price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price="9.00",
    )
    sek = set_price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.SEK,
        price="99.00",
    )

    assert {eur.currency, sek.currency} == {
        PriceAmount.Currency.EUR,
        PriceAmount.Currency.SEK,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("price", "original_price", "message"),
    [
        ("0.00", None, "price must be greater than zero"),
        ("-1.00", None, "price must be greater than zero"),
        ("9.00", "0.00", "original price must be greater than zero"),
        ("9.00", "5.00", "original price cannot be below current price"),
    ],
)
def test_set_price_amount_rejects_invalid_amounts(
    price,
    original_price,
    message,
):
    commercial_price = commercial_price_factory()

    with pytest.raises(
        InvalidCommercialPrice,
        match=message,
    ):
        set_price_amount(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
            price=price,
            original_price=original_price,
        )


@pytest.mark.django_db
def test_commercial_price_can_be_enabled_without_amount():
    commercial_price = commercial_price_factory(
        enabled=False,
    )

    commercial_price = set_commercial_price_enabled(
        commercial_price=commercial_price,
        enabled=True,
    )

    assert commercial_price.enabled
    assert commercial_price.amounts.count() == 0


@pytest.mark.django_db
def test_commercial_price_can_be_enabled_with_amount():
    commercial_price = commercial_price_factory(
        enabled=False,
    )

    set_price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price="9.00",
    )

    commercial_price = set_commercial_price_enabled(
        commercial_price=commercial_price,
        enabled=True,
    )

    assert commercial_price.enabled
    assert commercial_price.amounts.get(
        currency=PriceAmount.Currency.EUR,
    ).price == Decimal("9.00")


@pytest.mark.django_db
def test_commercial_price_can_be_disabled():
    commercial_price = commercial_price_factory(
        enabled=True,
    )

    commercial_price = set_commercial_price_enabled(
        commercial_price=commercial_price,
        enabled=False,
    )

    assert not commercial_price.enabled


@pytest.mark.django_db
def test_commercial_price_reason_can_be_changed():
    commercial_price = commercial_price_factory(
        reason="",
    )

    commercial_price = set_commercial_price_reason(
        commercial_price=commercial_price,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    assert commercial_price.reason == CommercialPrice.Reason.PROMOTION


@pytest.mark.django_db
def test_commercial_price_reason_rejects_unknown_choice():
    commercial_price = commercial_price_factory()

    with pytest.raises(
        InvalidCommercialPrice,
        match="invalid commercial price reason",
    ):
        set_commercial_price_reason(
            commercial_price=commercial_price,
            reason="mystery_reason",
        )
