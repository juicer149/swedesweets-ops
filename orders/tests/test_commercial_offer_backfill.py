from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from customers.tests.factories import customer_factory
from inventory.tests.factories import batch_factory
from products.tests.factories import product_factory


TODAY = timezone.localdate()

MIGRATE_FROM = [
    ("business", "0001_initial"),
    ("orders", "0010_orderline_commercial_offer"),
    ("pricing", "0002_create_business_standard_offers"),
    (
        "retail",
        (
            "0010_remove_retailcartline_"
            "unique_retail_commercial_price_per_cart_and_more"
        ),
    ),
]

MIGRATE_TO = [
    ("business", "0001_initial"),
    ("orders", "0011_backfill_order_line_commercial_offer"),
    ("pricing", "0002_create_business_standard_offers"),
    (
        "retail",
        (
            "0010_remove_retailcartline_"
            "unique_retail_commercial_price_per_cart_and_more"
        ),
    ),
]

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def historical_apps():
    executor = MigrationExecutor(connection)
    latest_targets = executor.loader.graph.leaf_nodes()

    executor.migrate(MIGRATE_FROM)
    apps = executor.loader.project_state(MIGRATE_FROM).apps

    try:
        yield apps
    finally:
        MigrationExecutor(connection).migrate(latest_targets)


@pytest.fixture
def product(historical_apps):
    return product_factory(internal_number=1)


@pytest.fixture
def business_order(historical_apps):
    customer = customer_factory()
    Order = historical_apps.get_model("orders", "Order")

    return Order.objects.create(customer_id=customer.pk)


def _migrate(targets):
    MigrationExecutor(connection).migrate(targets)


def _offer(
    apps,
    product,
    *,
    channel,
    batch=None,
):
    CommercialPrice = apps.get_model(
        "pricing",
        "CommercialPrice",
    )

    return CommercialPrice.objects.create(
        product_id=product.pk,
        batch_id=batch.pk if batch is not None else None,
        channel=channel,
        enabled=True,
    )


def _line(
    apps,
    order,
    product,
    *,
    quantity=5,
    commercial_offer=None,
):
    OrderLine = apps.get_model("orders", "OrderLine")

    return OrderLine.objects.create(
        order_id=order.pk,
        product_id=product.pk,
        quantity=quantity,
        unit="stock_unit",
        quantity_in_units=quantity,
        commercial_offer_id=(
            commercial_offer.pk
            if commercial_offer is not None
            else None
        ),
    )


def test_business_line_without_selection_gets_standard_offer(
    historical_apps,
    business_order,
    product,
):
    offer = _offer(
        historical_apps,
        product,
        channel="business",
    )
    line = _line(
        historical_apps,
        business_order,
        product,
    )

    _migrate(MIGRATE_TO)

    line.refresh_from_db()
    assert line.commercial_offer_id == offer.pk


def test_business_line_with_unpriced_standard_selection_gets_standard_offer(
    historical_apps,
    business_order,
    product,
):
    BusinessOfferSelection = historical_apps.get_model(
        "business",
        "BusinessOfferSelection",
    )

    offer = _offer(
        historical_apps,
        product,
        channel="business",
    )
    line = _line(
        historical_apps,
        business_order,
        product,
    )
    BusinessOfferSelection.objects.create(
        order_line_id=line.pk,
        commercial_price_id=None,
    )

    _migrate(MIGRATE_TO)

    line.refresh_from_db()
    assert line.commercial_offer_id == offer.pk


def test_explicit_business_selection_is_preserved(
    historical_apps,
    business_order,
    product,
):
    BusinessOfferSelection = historical_apps.get_model(
        "business",
        "BusinessOfferSelection",
    )

    _offer(
        historical_apps,
        product,
        channel="business",
    )

    batch = batch_factory(
        product=product,
        today=TODAY,
    )
    batch_offer = _offer(
        historical_apps,
        product,
        channel="business",
        batch=batch,
    )
    line = _line(
        historical_apps,
        business_order,
        product,
    )
    BusinessOfferSelection.objects.create(
        order_line_id=line.pk,
        commercial_price_id=batch_offer.pk,
    )

    _migrate(MIGRATE_TO)

    line.refresh_from_db()
    assert line.commercial_offer_id == batch_offer.pk


def test_explicit_retail_selection_is_preserved(
    historical_apps,
    product,
):
    Order = historical_apps.get_model("orders", "Order")
    RetailOfferSelection = historical_apps.get_model(
        "retail",
        "RetailOfferSelection",
    )

    retail_offer = _offer(
        historical_apps,
        product,
        channel="retail",
    )
    order = Order.objects.create(
        channel="retail",
        customer_id=None,
    )
    line = _line(
        historical_apps,
        order,
        product,
    )
    RetailOfferSelection.objects.create(
        order_line_id=line.pk,
        commercial_price_id=retail_offer.pk,
    )

    _migrate(MIGRATE_TO)

    line.refresh_from_db()
    assert line.commercial_offer_id == retail_offer.pk


def test_retail_line_without_selection_stops_the_migration(
    historical_apps,
    product,
):
    Order = historical_apps.get_model("orders", "Order")

    order = Order.objects.create(
        channel="retail",
        customer_id=None,
    )
    line = _line(
        historical_apps,
        order,
        product,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="none may be inferred",
        ):
            _migrate(MIGRATE_TO)

        line.refresh_from_db()
        assert line.commercial_offer_id is None
    finally:
        type(line).objects.filter(pk=line.pk).delete()


def test_business_line_without_standard_offer_stops_the_migration(
    historical_apps,
    business_order,
    product,
):
    line = _line(
        historical_apps,
        business_order,
        product,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="no standard BUSINESS offer",
        ):
            _migrate(MIGRATE_TO)

        line.refresh_from_db()
        assert line.commercial_offer_id is None
    finally:
        type(line).objects.filter(pk=line.pk).delete()


def test_already_resolved_lines_are_left_alone(
    historical_apps,
    business_order,
    product,
):
    standard_offer = _offer(
        historical_apps,
        product,
        channel="business",
    )

    batch = batch_factory(
        product=product,
        today=TODAY,
    )
    batch_offer = _offer(
        historical_apps,
        product,
        channel="business",
        batch=batch,
    )
    line = _line(
        historical_apps,
        business_order,
        product,
        commercial_offer=batch_offer,
    )

    _migrate(MIGRATE_TO)

    line.refresh_from_db()
    assert line.commercial_offer_id == batch_offer.pk
    assert line.commercial_offer_id != standard_offer.pk


def test_is_idempotent(
    historical_apps,
    business_order,
    product,
):
    offer = _offer(
        historical_apps,
        product,
        channel="business",
    )
    line = _line(
        historical_apps,
        business_order,
        product,
    )

    _migrate(MIGRATE_TO)
    _migrate(MIGRATE_FROM)
    _migrate(MIGRATE_TO)

    line.refresh_from_db()
    assert line.commercial_offer_id == offer.pk
