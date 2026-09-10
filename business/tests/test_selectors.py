from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from business.selectors import (
    list_business_catalog_entries,
    list_business_catalog_products,
)
from common.catalog.contracts import (
    CatalogOfferKind,
)
from inventory.models import InventoryBatch
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)
from products.models import Product


def _product(
    *,
    internal_number: int,
    name: str,
    active: bool = True,
) -> Product:
    return Product.objects.create(
        internal_number=internal_number,
        brand="SwedeSweets",
        name=name,
        weight_per_unit=1000,
        active=active,
    )


def _batch(
    *,
    product: Product,
    batch_id: str,
    quantity: int,
) -> InventoryBatch:
    return InventoryBatch.objects.create(
        batch_id=batch_id,
        product=product,
        quantity=quantity,
        best_before=(
            timezone.localdate()
            + timedelta(days=30)
        ),
        location="Warehouse",
        status=InventoryBatch.Status.ACTIVE,
    )


def _commercial_price(
    *,
    product: Product,
    channel: str,
    batch: InventoryBatch | None = None,
    enabled: bool = True,
    reason: str = "",
) -> CommercialPrice:
    return CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=channel,
        enabled=enabled,
        reason=reason,
    )


def _price_amount(
    *,
    commercial_price: CommercialPrice,
    currency: str = PriceAmount.Currency.EUR,
    price: str,
) -> PriceAmount:
    return PriceAmount.objects.create(
        commercial_price=commercial_price,
        currency=currency,
        price=Decimal(price),
    )


@pytest.mark.django_db
def test_business_catalog_lists_active_products_with_stock(
    monkeypatch,
):
    first = _product(
        internal_number=1,
        name="First",
    )
    second = _product(
        internal_number=2,
        name="Second",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            first.id: 8,
            second.id: 3,
        },
    )

    entries = list_business_catalog_entries()

    assert tuple(
        entry.product
        for entry in entries
    ) == (
        first,
        second,
    )

    assert tuple(
        entry.available_units
        for entry in entries
    ) == (
        8,
        3,
    )


@pytest.mark.django_db
def test_business_catalog_excludes_product_without_stock(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Unavailable",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 0,
        },
    )

    assert list_business_catalog_entries() == ()


@pytest.mark.django_db
def test_business_catalog_excludes_inactive_product(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Inactive",
        active=False,
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    assert list_business_catalog_entries() == ()


@pytest.mark.django_db
def test_business_catalog_prefetches_translations(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Translated later",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 4,
        },
    )

    (entry,) = list_business_catalog_entries()

    assert hasattr(
        entry.product,
        "prefetched_translations",
    )


@pytest.mark.django_db
def test_business_catalog_product_has_unpriced_standard_offer(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Ordinary",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 8,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {},
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert catalog_product.product == product
    assert catalog_product.available_units == 8

    assert len(catalog_product.offers) == 1

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.STANDARD
    assert offer.commercial_price_id is None
    assert offer.batch_id is None
    assert offer.reason is None
    assert offer.price is None
    assert offer.currency == PriceAmount.Currency.EUR
    assert offer.available_units == 8


@pytest.mark.django_db
def test_business_catalog_standard_offer_uses_enabled_business_price(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Priced",
    )

    commercial_price = _commercial_price(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
    )

    amount = _price_amount(
        commercial_price=commercial_price,
        price="12.50",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {},
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.STANDARD
    assert (
        offer.commercial_price_id
        == commercial_price.pk
    )
    assert offer.batch_id is None
    assert offer.price == amount.price
    assert offer.currency == PriceAmount.Currency.EUR
    assert offer.available_units == 10


@pytest.mark.django_db
def test_business_catalog_adds_enabled_business_batch_offer(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Batch offer",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-001",
        quantity=4,
    )

    commercial_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    amount = _price_amount(
        commercial_price=commercial_price,
        price="8.50",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {
            batch.pk: 4,
        },
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert catalog_product.available_units == 10
    assert len(catalog_product.offers) == 2

    standard_offer, batch_offer = (
        catalog_product.offers
    )

    assert (
        standard_offer.kind
        == CatalogOfferKind.STANDARD
    )
    assert standard_offer.available_units == 6

    assert (
        batch_offer.kind
        == CatalogOfferKind.BATCH
    )
    assert (
        batch_offer.commercial_price_id
        == commercial_price.pk
    )
    assert batch_offer.batch_id == batch.pk
    assert (
        batch_offer.reason
        == CommercialPrice.Reason.SHORT_DATED
    )
    assert batch_offer.price == amount.price
    assert (
        batch_offer.currency
        == PriceAmount.Currency.EUR
    )
    assert batch_offer.available_units == 4


@pytest.mark.django_db
def test_business_catalog_ignores_retail_batch_offer(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Retail only offer",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-002",
        quantity=4,
    )

    retail_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    _price_amount(
        commercial_price=retail_price,
        price="7.50",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {},
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert len(catalog_product.offers) == 1

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.STANDARD
    assert offer.available_units == 10


@pytest.mark.django_db
def test_business_catalog_ignores_disabled_business_batch_offer(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Disabled offer",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-003",
        quantity=4,
    )

    commercial_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    _price_amount(
        commercial_price=commercial_price,
        price="6.50",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {},
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert len(catalog_product.offers) == 1

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.STANDARD
    assert offer.available_units == 10


@pytest.mark.django_db
def test_business_catalog_ignores_batch_offer_without_eur_amount(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="SEK only",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-004",
        quantity=4,
    )

    commercial_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    _price_amount(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.SEK,
        price="95.00",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {},
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert len(catalog_product.offers) == 1

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.STANDARD
    assert offer.available_units == 10


@pytest.mark.django_db
def test_business_batch_offer_uses_available_not_physical_quantity(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Reserved stock",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-005",
        quantity=6,
    )

    commercial_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    _price_amount(
        commercial_price=commercial_price,
        price="5.00",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {
            batch.pk: 2,
        },
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    standard_offer, batch_offer = (
        catalog_product.offers
    )

    assert standard_offer.available_units == 8
    assert batch_offer.available_units == 2


@pytest.mark.django_db
def test_business_catalog_excludes_batch_offer_without_available_stock(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Sold out offer",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-006",
        quantity=4,
    )

    commercial_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    _price_amount(
        commercial_price=commercial_price,
        price="5.00",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 10,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {
            batch.pk: 0,
        },
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert len(catalog_product.offers) == 1

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.STANDARD
    assert offer.available_units == 10


@pytest.mark.django_db
def test_business_catalog_can_expose_only_batch_offer(
    monkeypatch,
):
    product = _product(
        internal_number=1,
        name="Special stock only",
    )

    batch = _batch(
        product=product,
        batch_id="BATCH-007",
        quantity=5,
    )

    commercial_price = _commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    _price_amount(
        commercial_price=commercial_price,
        price="4.50",
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_product_id",
        lambda: {
            product.id: 5,
        },
    )

    monkeypatch.setattr(
        "business.selectors.orderable_quantity_by_batch_pk",
        lambda *, batch_pks: {
            batch.pk: 5,
        },
    )

    (catalog_product,) = (
        list_business_catalog_products()
    )

    assert catalog_product.available_units == 5
    assert len(catalog_product.offers) == 1

    (offer,) = catalog_product.offers

    assert offer.kind == CatalogOfferKind.BATCH
    assert offer.batch_id == batch.pk
    assert offer.available_units == 5
