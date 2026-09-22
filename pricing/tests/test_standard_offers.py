from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.tests.factories import batch_factory
from pricing.errors import InvalidCommercialPrice
from pricing.models import CommercialPrice, PriceAmount
from pricing.services import ensure_standard_offer
from products.tests.factories import product_factory

TODAY = timezone.localdate()


def _product_level_offers(product):
    return CommercialPrice.objects.filter(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        batch__isnull=True,
    )


@pytest.mark.django_db
def test_creates_enabled_unpriced_business_standard_offer():
    product = product_factory()

    offer = ensure_standard_offer(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    assert offer.product == product
    assert offer.batch_id is None
    assert offer.channel == CommercialPrice.Channel.BUSINESS
    assert offer.reason == ""
    assert offer.enabled is True
    assert not offer.amounts.exists()


@pytest.mark.django_db
def test_is_idempotent():
    product = product_factory()

    first = ensure_standard_offer(
        product=product, channel=CommercialPrice.Channel.BUSINESS,
    )
    second = ensure_standard_offer(
        product=product, channel=CommercialPrice.Channel.BUSINESS,
    )

    assert first.pk == second.pk
    assert _product_level_offers(product).count() == 1


@pytest.mark.django_db
def test_does_not_re_enable_existing_disabled_offer():
    product = product_factory()
    existing = CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
    )

    offer = ensure_standard_offer(
        product=product, channel=CommercialPrice.Channel.BUSINESS,
    )

    offer.refresh_from_db()
    assert offer.pk == existing.pk
    assert offer.enabled is False


@pytest.mark.django_db
def test_does_not_touch_existing_reason_or_amounts():
    product = product_factory()
    existing = CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
        reason=CommercialPrice.Reason.PROMOTION,
    )
    PriceAmount.objects.create(
        commercial_price=existing,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("12.50"),
    )

    offer = ensure_standard_offer(
        product=product, channel=CommercialPrice.Channel.BUSINESS,
    )

    offer.refresh_from_db()
    assert offer.reason == CommercialPrice.Reason.PROMOTION
    assert list(offer.amounts.values_list("currency", "price")) == [
        (PriceAmount.Currency.EUR, Decimal("12.50")),
    ]


@pytest.mark.django_db
def test_batch_specific_offer_does_not_count_as_standard_offer():
    product = product_factory()
    batch = batch_factory(product=product, today=TODAY)
    batch_offer = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    offer = ensure_standard_offer(
        product=product, channel=CommercialPrice.Channel.BUSINESS,
    )

    assert offer.pk != batch_offer.pk
    assert offer.batch_id is None
    assert _product_level_offers(product).count() == 1


@pytest.mark.django_db
def test_retail_channel_is_rejected():
    product = product_factory()

    with pytest.raises(InvalidCommercialPrice, match="business channel"):
        ensure_standard_offer(
            product=product, channel=CommercialPrice.Channel.RETAIL,
        )

    assert not CommercialPrice.objects.filter(product=product).exists()
