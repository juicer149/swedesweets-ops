from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.tests.factories import batch_factory
from ops_portal.inventory.pricing_services import (
    update_batch_special_pricing,
)
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import (
    get_batch_commercial_price,
    get_product_commercial_price,
)
from pricing.services import (
    create_commercial_price,
    set_commercial_price_enabled,
    set_price_amount,
)
from products.tests.factories import product_factory


TODAY = timezone.localdate()


@pytest.mark.django_db
def test_update_batch_special_pricing_empty_input_creates_nothing():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason="",
        business_eur=None,
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    assert CommercialPrice.objects.filter(
        batch=batch
    ).count() == 0


@pytest.mark.django_db
def test_update_batch_special_pricing_creates_business_price():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert commercial_price is not None
    assert commercial_price.product == product
    assert commercial_price.batch == batch
    assert (
        commercial_price.reason
        == CommercialPrice.Reason.SHORT_DATED
    )
    assert commercial_price.enabled is True

    amount = commercial_price.amounts.get(
        currency=PriceAmount.Currency.EUR
    )

    assert amount.price == Decimal("4.50")


@pytest.mark.django_db
def test_update_batch_special_pricing_creates_retail_price():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.PROMOTION,
        business_eur=None,
        business_sek=None,
        business_enabled=False,
        retail_eur=Decimal("5.25"),
        retail_sek=Decimal("57.00"),
        retail_enabled=True,
    )

    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
    )

    assert commercial_price is not None
    assert (
        commercial_price.reason
        == CommercialPrice.Reason.PROMOTION
    )
    assert commercial_price.enabled is True

    assert commercial_price.amounts.get(
        currency=PriceAmount.Currency.EUR
    ).price == Decimal("5.25")

    assert commercial_price.amounts.get(
        currency=PriceAmount.Currency.SEK
    ).price == Decimal("57.00")


@pytest.mark.django_db
def test_update_batch_special_pricing_creates_both_channels():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=Decimal("49.00"),
        business_enabled=True,
        retail_eur=Decimal("5.50"),
        retail_sek=Decimal("59.00"),
        retail_enabled=True,
    )

    assert CommercialPrice.objects.filter(
        batch=batch
    ).count() == 2

    assert get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    ) is not None

    assert get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
    ) is not None


@pytest.mark.django_db
def test_update_batch_special_pricing_updates_existing_amount():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("3.75"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert commercial_price is not None

    amount = commercial_price.amounts.get(
        currency=PriceAmount.Currency.EUR
    )

    assert amount.price == Decimal("3.75")


@pytest.mark.django_db
def test_update_batch_special_pricing_removes_cleared_amount():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=Decimal("49.00"),
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert commercial_price is not None
    assert not commercial_price.amounts.filter(
        currency=PriceAmount.Currency.SEK
    ).exists()

    assert commercial_price.amounts.get(
        currency=PriceAmount.Currency.EUR
    ).price == Decimal("4.50")


@pytest.mark.django_db
def test_update_batch_special_pricing_disables_existing_channel():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert commercial_price is not None
    assert commercial_price.enabled is False


@pytest.mark.django_db
def test_update_batch_special_pricing_updates_reason():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.DAMAGED_PACKAGE,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=False,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    commercial_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert commercial_price is not None
    assert (
        commercial_price.reason
        == CommercialPrice.Reason.DAMAGED_PACKAGE
    )


@pytest.mark.django_db
def test_update_batch_special_pricing_does_not_touch_product_wide_price():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    product_price = create_commercial_price(
        product=product,
        batch=None,
        channel=CommercialPrice.Channel.BUSINESS,
    )
    set_price_amount(
        commercial_price=product_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("10.00"),
    )
    product_price = set_commercial_price_enabled(
        commercial_price=product_price,
        enabled=True,
    )

    update_batch_special_pricing(
        batch=batch,
        reason=CommercialPrice.Reason.SHORT_DATED,
        business_eur=Decimal("4.50"),
        business_sek=None,
        business_enabled=True,
        retail_eur=None,
        retail_sek=None,
        retail_enabled=False,
    )

    product_price.refresh_from_db()

    assert product_price.batch_id is None
    assert product_price.enabled is True

    assert product_price.amounts.get(
        currency=PriceAmount.Currency.EUR
    ).price == Decimal("10.00")

    batch_price = get_batch_commercial_price(
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert batch_price is not None
    assert batch_price.pk != product_price.pk
    assert batch_price.batch == batch

    product_wide_price = get_product_commercial_price(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert product_wide_price is not None
    assert product_wide_price.pk == product_price.pk
