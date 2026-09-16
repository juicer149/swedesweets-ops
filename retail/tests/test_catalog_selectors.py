from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from common.catalog.contracts import CatalogOfferKind
from pricing.models import CommercialPrice, PriceAmount
from retail.catalog_selectors import (
    get_retail_catalog_product,
    list_retail_catalog_products,
)
from retail.tests.factories import (
    retail_batch_price_factory,
    retail_inventory_batch_factory,
    retail_product_factory,
    retail_product_price_factory,
)


@pytest.mark.django_db
def test_enabled_priced_product_with_stock_appears_in_catalog():
    product = retail_product_factory()
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    retail_inventory_batch_factory(
        product=product,
        quantity=10,
    )

    catalog_products = (
        list_retail_catalog_products()
    )

    assert len(catalog_products) == 1

    catalog_product = catalog_products[0]

    assert catalog_product.product == product
    assert catalog_product.available_units == 10

    [catalog_offer] = catalog_product.offers

    assert (
        catalog_offer.commercial_price_id
        == offer.pk
    )
    assert (
        catalog_offer.kind
        == CatalogOfferKind.STANDARD
    )
    assert catalog_offer.price == Decimal(
        "6.90"
    )
    assert catalog_offer.available_units == 10


@pytest.mark.django_db
def test_product_with_only_business_price_does_not_appear():
    product = retail_product_factory()

    business_price = CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    PriceAmount.objects.create(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("6.90"),
    )
    retail_inventory_batch_factory(
        product=product,
        quantity=10,
    )

    assert list_retail_catalog_products() == ()


@pytest.mark.django_db
def test_disabled_retail_price_does_not_appear():
    product = retail_product_factory()
    retail_product_price_factory(
        product=product,
        enabled=False,
        price=Decimal("6.90"),
    )
    retail_inventory_batch_factory(
        product=product,
        quantity=10,
    )

    assert list_retail_catalog_products() == ()


@pytest.mark.django_db
def test_priced_product_without_stock_does_not_appear():
    product = retail_product_factory()
    retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    # No inventory batch created - zero available units.

    assert list_retail_catalog_products() == ()


@pytest.mark.django_db
def test_batch_price_excludes_its_batch_from_the_standard_pool():
    today = timezone.localdate()
    product = retail_product_factory()

    retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    ordinary = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="ORDINARY",
        quantity=10,
        best_before=today + timedelta(days=30),
    )
    special = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="SPECIAL",
        quantity=4,
        best_before=today + timedelta(days=5),
    )
    retail_batch_price_factory(
        batch=special,
        enabled=True,
        price=Decimal("3.90"),
    )

    [catalog_product] = list_retail_catalog_products()

    assert catalog_product.available_units == (
        ordinary.quantity + special.quantity
    )

    offers_by_kind = {
        offer.kind: offer
        for offer in catalog_product.offers
    }

    assert (
        offers_by_kind[
            CatalogOfferKind.STANDARD
        ].available_units
        == ordinary.quantity
    )
    assert (
        offers_by_kind[
            CatalogOfferKind.BATCH
        ].available_units
        == special.quantity
    )
    assert (
        offers_by_kind[
            CatalogOfferKind.BATCH
        ].batch_id
        == special.pk
    )


@pytest.mark.django_db
def test_get_retail_catalog_product_returns_matching_product():
    product = retail_product_factory()
    retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )
    retail_inventory_batch_factory(
        product=product,
        quantity=10,
    )

    catalog_product = get_retail_catalog_product(
        product_id=product.id,
    )

    assert catalog_product is not None
    assert catalog_product.product == product


@pytest.mark.django_db
def test_get_retail_catalog_product_returns_none_for_unknown_product():
    assert (
        get_retail_catalog_product(
            product_id=999999,
        )
        is None
    )
