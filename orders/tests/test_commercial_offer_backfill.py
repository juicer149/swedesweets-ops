from __future__ import annotations

import importlib
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.utils import timezone

from business.models import BusinessOfferSelection
from inventory.tests.factories import batch_factory
from orders.models import Order, OrderLine
from pricing.models import CommercialPrice, PriceAmount
from products.tests.factories import product_factory
from retail.models import RetailOfferSelection

TODAY = timezone.localdate()

migration = importlib.import_module(
    "orders.migrations.0011_backfill_order_line_commercial_offer"
)

SCHEMA_EDITOR = SimpleNamespace(connection=SimpleNamespace(alias="default"))


def _run():
    migration.backfill_commercial_offers(apps, SCHEMA_EDITOR)


def _standard_offer(product):
    return CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )


def _line(order, product, *, quantity=5):
    return OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
    )


@pytest.fixture
def product():
    return product_factory(internal_number=1)


@pytest.fixture
def business_order(customer):
    return Order.objects.create(customer=customer)


@pytest.mark.django_db
def test_business_line_without_selection_gets_standard_offer(
    business_order,
    product,
):
    offer = _standard_offer(product)
    line = _line(business_order, product)

    _run()

    line.refresh_from_db()
    assert line.commercial_offer == offer


@pytest.mark.django_db
def test_business_line_with_unpriced_standard_selection_gets_standard_offer(
    business_order,
    product,
):
    offer = _standard_offer(product)
    line = _line(business_order, product)
    BusinessOfferSelection.objects.create(
        order_line=line,
        commercial_price=None,
    )

    _run()

    line.refresh_from_db()
    assert line.commercial_offer == offer


@pytest.mark.django_db
def test_explicit_business_selection_is_preserved(
    business_order,
    product,
):
    _standard_offer(product)
    batch = batch_factory(product=product, today=TODAY)
    batch_offer = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    line = _line(business_order, product)
    BusinessOfferSelection.objects.create(
        order_line=line,
        commercial_price=batch_offer,
    )

    _run()

    line.refresh_from_db()
    assert line.commercial_offer == batch_offer


@pytest.mark.django_db
def test_explicit_retail_selection_is_preserved(product):
    retail_offer = CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    PriceAmount.objects.create(
        commercial_price=retail_offer,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("3.00"),
    )
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = _line(order, product)
    RetailOfferSelection.objects.create(
        order_line=line,
        commercial_price=retail_offer,
    )

    _run()

    line.refresh_from_db()
    assert line.commercial_offer == retail_offer


@pytest.mark.django_db
def test_retail_line_without_selection_stops_the_migration(product):
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = _line(order, product)

    with pytest.raises(RuntimeError, match="none may be inferred"):
        _run()

    line.refresh_from_db()
    assert line.commercial_offer is None


@pytest.mark.django_db
def test_business_line_without_standard_offer_stops_the_migration(
    business_order,
    product,
):
    line = _line(business_order, product)

    with pytest.raises(RuntimeError, match="no standard BUSINESS offer"):
        _run()

    line.refresh_from_db()
    assert line.commercial_offer is None


@pytest.mark.django_db
def test_already_resolved_lines_are_left_alone(
    business_order,
    product,
):
    standard_offer = _standard_offer(product)
    batch = batch_factory(product=product, today=TODAY)
    batch_offer = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    line = _line(business_order, product)
    line.commercial_offer = batch_offer
    line.save(update_fields=["commercial_offer"])

    _run()

    line.refresh_from_db()
    assert line.commercial_offer == batch_offer
    assert line.commercial_offer != standard_offer


@pytest.mark.django_db
def test_is_idempotent(business_order, product):
    offer = _standard_offer(product)
    line = _line(business_order, product)

    _run()
    _run()

    line.refresh_from_db()
    assert line.commercial_offer == offer
