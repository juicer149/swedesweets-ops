from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.tests.factories import batch_factory
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import list_orderable_batches_for_offer
from products.tests.factories import product_factory

TODAY = timezone.localdate()


def _offer(
    *,
    product,
    channel,
    batch=None,
    enabled=True,
    currency=PriceAmount.Currency.EUR,
    price="6.90",
):
    offer = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=channel,
        enabled=enabled,
    )
    if price is not None:
        PriceAmount.objects.create(
            commercial_price=offer,
            currency=currency,
            price=Decimal(price),
        )
    return offer


@pytest.mark.django_db
def test_product_offer_returns_ordinary_pool():
    product = product_factory()
    batch = batch_factory(product=product, today=TODAY)
    offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [batch]


@pytest.mark.django_db
def test_batch_offer_returns_exact_batch_only():
    product = product_factory()
    batch_factory(product=product, today=TODAY, batch_id="OTHER")
    target = batch_factory(product=product, today=TODAY, batch_id="TARGET")
    offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL, batch=target)

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [target]


@pytest.mark.django_db
def test_product_offer_excludes_batch_with_own_enabled_same_channel_offer():
    product = product_factory()
    ordinary = batch_factory(product=product, today=TODAY, batch_id="ORDINARY")
    special = batch_factory(product=product, today=TODAY, batch_id="SPECIAL")
    product_offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)
    _offer(product=product, channel=CommercialPrice.Channel.RETAIL, batch=special)

    assert list(
        list_orderable_batches_for_offer(
            offer=product_offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [ordinary]


@pytest.mark.django_db
def test_other_channels_batch_offer_does_not_affect_this_pool():
    product = product_factory()
    batch = batch_factory(product=product, today=TODAY)
    retail_offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)
    _offer(product=product, channel=CommercialPrice.Channel.BUSINESS, batch=batch)

    assert list(
        list_orderable_batches_for_offer(
            offer=retail_offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [batch]


@pytest.mark.django_db
def test_batch_offer_with_no_amount_does_not_remove_batch_from_pool():
    """An enabled batch offer with no priced amount is not yet a sellable
    special offer, so its batch stays claimable through the product offer."""

    product = product_factory()
    batch = batch_factory(product=product, today=TODAY)
    product_offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)
    _offer(
        product=product, channel=CommercialPrice.Channel.RETAIL,
        batch=batch, price=None,
    )

    assert list(
        list_orderable_batches_for_offer(
            offer=product_offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [batch]


@pytest.mark.django_db
def test_disabled_offer_has_no_pool():
    product = product_factory()
    batch_factory(product=product, today=TODAY)
    offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL, enabled=False)

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == []


@pytest.mark.django_db
def test_offer_for_inactive_product_has_no_pool():
    product = product_factory()
    batch_factory(product=product, today=TODAY)
    offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)
    product.active = False
    product.save(update_fields=["active"])

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == []


@pytest.mark.django_db
def test_expired_batch_is_excluded():
    product = product_factory()
    created_on = TODAY - timedelta(days=10)
    batch_factory(
        product=product,
        today=created_on,
        best_before=created_on + timedelta(days=1),
    )
    offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == []


@pytest.mark.django_db
def test_wrong_currency_still_shows_product_pool_but_not_the_exclusion():
    """The offer's own currency is the caller's problem; the pool selector
    only cares which currency the *excluded* batch's own offer is priced in."""

    product = product_factory()
    ordinary = batch_factory(product=product, today=TODAY, batch_id="ORDINARY")
    special = batch_factory(product=product, today=TODAY, batch_id="SPECIAL")
    product_offer = _offer(
        product=product, channel=CommercialPrice.Channel.RETAIL, currency="SEK",
    )
    _offer(
        product=product, channel=CommercialPrice.Channel.RETAIL,
        batch=special, currency=PriceAmount.Currency.SEK,
    )

    assert list(
        list_orderable_batches_for_offer(
            offer=product_offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [ordinary, special]


@pytest.mark.django_db
def test_product_offer_uses_fefo_order():
    product = product_factory()
    later = batch_factory(
        product=product, today=TODAY, batch_id="LATER",
        best_before=TODAY + timedelta(days=60),
    )
    earlier = batch_factory(
        product=product, today=TODAY, batch_id="EARLIER",
        best_before=TODAY + timedelta(days=20),
    )
    offer = _offer(product=product, channel=CommercialPrice.Channel.RETAIL)

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [earlier, later]


@pytest.mark.django_db
def test_unpriced_business_standard_offer_still_resolves_pool():
    """An offer with enabled=True but no PriceAmount at all (the business
    standard-offer shape from step 2b) still has a resolvable pool - pricing
    is a separate concern the caller checks on its own."""

    product = product_factory()
    batch = batch_factory(product=product, today=TODAY)
    offer = _offer(
        product=product, channel=CommercialPrice.Channel.BUSINESS, price=None,
    )

    assert list(
        list_orderable_batches_for_offer(
            offer=offer, currency=PriceAmount.Currency.EUR, today=TODAY,
        )
    ) == [batch]
