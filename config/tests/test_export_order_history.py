from __future__ import annotations

import hashlib
import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from business.models import BusinessOfferSelection
from customers.tests.factories import customer_factory
from inventory.tests.factories import batch_factory
from orders.models import Order, OrderLine
from pricing.models import CommercialPrice
from products.tests.factories import product_factory
from retail.models import RetailOfferSelection

TODAY = timezone.localdate()


def _export(tmp_path, **options):
    output_dir = tmp_path / "export"
    call_command("export_order_history", output_dir=str(output_dir), **options)
    return output_dir


def _read(output_dir):
    return json.loads((output_dir / "orders.json").read_text())


def _line(order, product, *, quantity=10, unit_price=None):
    return OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
        unit_price_snapshot=unit_price,
    )


@pytest.fixture
def customer():
    return customer_factory(
        name="Ica Ugglebo",
        email="ICA@EXAMPLE.SE",
        phone_number="+46 123-456-789",
        country="FR",
        city="Paris",
        address_line="Example Street 1",
    )


@pytest.fixture
def apple():
    return product_factory(name="Apple", internal_number=1)


@pytest.mark.django_db
def test_export_covers_legacy_explicit_retail_and_cancelled_orders(
    tmp_path,
    customer,
    apple,
):
    user = get_user_model().objects.create_user(username="ops1", password="x")
    batch = batch_factory(product=apple, today=TODAY, batch_id="A-001")

    # 1. legacy B2B line: no selection row, no price
    legacy = Order.objects.create(customer=customer)
    legacy.mark_as_placed(user=user)
    _line(legacy, apple)

    # 2. B2B line with an explicit batch-specific offer and a price snapshot
    explicit = Order.objects.create(customer=customer)
    explicit.mark_as_placed(user=user)
    explicit_line = _line(explicit, apple, quantity=4, unit_price="2.50")
    batch_offer = CommercialPrice.objects.create(
        product=apple,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    BusinessOfferSelection.objects.create(
        order_line=explicit_line,
        commercial_price=batch_offer,
    )

    # 3. anonymous retail order with a product-level offer
    retail = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
        buyer_name_snapshot="Anna Buyer",
        buyer_email_snapshot="anna@example.com",
    )
    retail_line = _line(retail, apple, quantity=2, unit_price="3.00")
    retail_offer = CommercialPrice.objects.create(
        product=apple,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    RetailOfferSelection.objects.create(
        order_line=retail_line,
        commercial_price=retail_offer,
    )

    # 4. cancelled order
    cancelled = Order.objects.create(customer=customer)
    cancelled.mark_as_placed(user=user)
    _line(cancelled, apple)
    cancelled.cancel(
        user=user,
        reason=Order.CancelReason.CUSTOMER_REQUEST,
        note="  changed mind ",
    )

    data = _read(_export(tmp_path))
    by_id = {order["source_order_id"]: order for order in data["orders"]}

    assert data["format"] == "swedesweets-order-history"
    assert data["counts"]["orders"] == 4
    assert data["counts"]["order_lines"] == 4
    assert data["counts"]["order_lines_with_explicit_offer"] == 2
    assert data["counts"]["orders_by_status"] == {
        "cancelled": 1,
        "draft": 1,
        "placed": 2,
    }
    assert data["counts"]["database"]["orders"] == 4

    legacy_record = by_id[legacy.id]
    assert legacy_record["customer"] == {
        "email": "ica@example.se",
        "name": "Ica Ugglebo",
    }
    assert legacy_record["lines"][0]["offer"] is None
    assert legacy_record["lines"][0]["unit_price_snapshot"] is None
    assert legacy_record["total"] is None
    assert legacy_record["actors"]["placed"] == "ops1"

    explicit_record = by_id[explicit.id]
    assert explicit_record["lines"][0]["offer"] == {
        "channel": "business",
        "product": {"sku": apple.sku, "internal_number": 1},
        "batch_id": "A-001",
    }
    assert explicit_record["lines"][0]["unit_price_snapshot"] == "2.50"
    assert explicit_record["lines"][0]["line_total"] == "10.00"
    assert explicit_record["total"] == "10.00"

    retail_record = by_id[retail.id]
    assert retail_record["customer"] is None
    assert retail_record["buyer"]["name"] == "Anna Buyer"
    assert retail_record["lines"][0]["offer"] == {
        "channel": "retail",
        "product": {"sku": apple.sku, "internal_number": 1},
        "batch_id": None,
    }

    cancelled_record = by_id[cancelled.id]
    assert cancelled_record["status"] == "cancelled"
    assert cancelled_record["cancel_reason"] == "customer_request"
    assert cancelled_record["cancel_note"] == "changed mind"
    assert cancelled_record["actors"]["cancelled"] == "ops1"
    assert cancelled_record["cancelled_at"] is not None


@pytest.mark.django_db
def test_export_writes_checksum_and_private_file(tmp_path, customer):
    Order.objects.create(customer=customer)

    output_dir = _export(tmp_path)
    data = (output_dir / "orders.json").read_bytes()
    checksum_line = (output_dir / "orders.json.sha256").read_text().strip()

    assert checksum_line == f"{hashlib.sha256(data).hexdigest()}  orders.json"
    assert (output_dir / "orders.json").stat().st_mode & 0o077 == 0


@pytest.mark.django_db
def test_export_refuses_to_overwrite_without_flag(tmp_path, customer):
    Order.objects.create(customer=customer)
    _export(tmp_path)

    with pytest.raises(CommandError, match="already exists"):
        _export(tmp_path)

    _export(tmp_path, overwrite=True)


@pytest.mark.django_db
def test_export_refuses_to_write_inside_repository(settings):
    inside = settings.BASE_DIR / "should_not_be_created"

    with pytest.raises(CommandError, match="outside the repo"):
        call_command("export_order_history", output_dir=str(inside))

    assert not inside.exists()


@pytest.mark.django_db
def test_export_of_empty_database_is_valid(tmp_path):
    data = _read(_export(tmp_path))

    assert data["orders"] == []
    assert data["counts"]["orders"] == 0
