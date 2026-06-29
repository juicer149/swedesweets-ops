from __future__ import annotations

from datetime import timedelta

import pytest

from inventory.expiry import (
    EXPIRY_CRITICAL_DAYS,
    EXPIRY_SOON_DAYS,
    ExpiryState,
    build_expiry_info,
)
from inventory.models import InventoryBatch
from inventory.selectors import (
    available_quantity_by_product,
    available_quantity_by_product_id,
    count_expiring_batches,
    count_low_stock_products,
    list_available_batches,
    list_available_batches_for_product,
    list_batch_rows,
    list_batches,
    list_depleted_batches,
    list_expiring_batch_rows_for_dashboard,
    list_low_stock_products_for_dashboard,
    orderable_quantity_by_product_id,
    physical_quantity_by_product,
)
from inventory.services import create_batch
from inventory.tests.conftest import TODAY


@pytest.mark.parametrize(
    ("days_from_today", "expected_state", "expected_label"),
    [
        (-1, ExpiryState.EXPIRED, "Expired"),
        (0, ExpiryState.CRITICAL, "Expires today"),
        (
            EXPIRY_CRITICAL_DAYS,
            ExpiryState.CRITICAL,
            f"Expires in {EXPIRY_CRITICAL_DAYS} days",
        ),
        (
            EXPIRY_CRITICAL_DAYS + 1,
            ExpiryState.SOON,
            f"Expires in {EXPIRY_CRITICAL_DAYS + 1} days",
        ),
        (
            EXPIRY_SOON_DAYS,
            ExpiryState.SOON,
            f"Expires in {EXPIRY_SOON_DAYS} days",
        ),
        (
            EXPIRY_SOON_DAYS + 1,
            ExpiryState.SAFE,
            "Best before",
        ),
    ],
)
def test_build_expiry_info_classifies_expiry_state(
    days_from_today,
    expected_state,
    expected_label,
):
    expiry = build_expiry_info(
        best_before=TODAY + timedelta(days=days_from_today),
        today=TODAY,
    )

    assert expiry.state is expected_state
    assert expiry.label == expected_label
    assert expiry.days_left == days_from_today


@pytest.mark.django_db
def test_list_batches_defaults_to_best_before_order(apple, batch_factory):
    batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=50,
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
    )

    batches = list(list_batches())

    assert [batch.batch_id for batch in batches] == ["A-001", "A-002"]


@pytest.mark.django_db
def test_list_batches_filters_by_valid_status(apple, batch_factory):
    active_batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
    )
    depleted_batch = batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=1,
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )
    depleted_batch.pick(quantity=1)

    batches = list(list_batches(status=InventoryBatch.Status.DEPLETED))

    assert active_batch not in batches
    assert depleted_batch in batches


@pytest.mark.django_db
def test_list_batch_rows_adds_expiry_info(apple, batch_factory):
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
        best_before=TODAY + timedelta(days=EXPIRY_CRITICAL_DAYS),
    )

    rows = list_batch_rows(today=TODAY)

    assert len(rows) == 1
    assert rows[0].batch.batch_id == "A-001"
    assert rows[0].expiry.state is ExpiryState.CRITICAL


@pytest.mark.django_db
def test_physical_quantity_by_product_sums_only_active_available_batches(
    apple,
    banana,
    batch_factory,
):
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
    )
    depleted = batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=1,
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )
    depleted.pick(quantity=1)
    batch_factory(
        product=banana,
        batch_id="B-001",
        quantity=80,
        best_before=TODAY + timedelta(days=75),
        location="Shelf B1",
    )

    rows = physical_quantity_by_product()
    quantity_by_sku = {row.sku: row.quantity for row in rows}

    assert quantity_by_sku == {
        "GENERIC-APPLE-5000": 100,
        "GENERIC-BANANA-6000": 80,
    }


@pytest.mark.django_db
def test_available_quantity_by_product_matches_physical_stock_without_reservations(
    stocked_inventory,
):
    rows = available_quantity_by_product()
    available_by_sku = {row.sku: row.available_quantity for row in rows}

    assert available_by_sku == {
        "GENERIC-APPLE-5000": 150,
        "GENERIC-BANANA-6000": 80,
    }


@pytest.mark.django_db
def test_available_quantity_by_product_id_returns_mapping(
    stocked_inventory, apple, banana
):
    available = available_quantity_by_product_id()

    assert available == {
        apple.id: 150,
        banana.id: 80,
    }


@pytest.mark.django_db
def test_orderable_quantity_by_product_id_excludes_expired_batches(apple):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )
    create_batch(
        batch_id="A-002",
        product=apple,
        quantity=50,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A2",
        today=TODAY,
    )

    assert orderable_quantity_by_product_id(today=TODAY) == {
        apple.id: 50,
    }


@pytest.mark.django_db
def test_list_available_batches_for_product_returns_active_batches_in_fefo_order(
    apple,
    banana,
    batch_factory,
):
    batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=50,
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
    )
    batch_factory(
        product=banana,
        batch_id="B-001",
        quantity=80,
        best_before=TODAY + timedelta(days=75),
        location="Shelf B1",
    )

    batches = list_available_batches_for_product(product=apple)

    assert [batch.batch_id for batch in batches] == ["A-001", "A-002"]


@pytest.mark.django_db
def test_list_available_batches_returns_active_batches_ordered_by_product_and_fefo(
    apple,
    banana,
    batch_factory,
):
    batch_factory(
        product=banana,
        batch_id="B-001",
        quantity=80,
        best_before=TODAY + timedelta(days=75),
        location="Shelf B1",
    )
    batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=50,
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
    )

    batches = list_available_batches()

    assert [(batch.product.sku, batch.batch_id) for batch in batches] == [
        ("GENERIC-APPLE-5000", "A-001"),
        ("GENERIC-APPLE-5000", "A-002"),
        ("GENERIC-BANANA-6000", "B-001"),
    ]


@pytest.mark.django_db
def test_list_depleted_batches_returns_only_depleted_batches(apple, batch_factory):
    active_batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
    )
    depleted_batch = batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=1,
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )

    depleted_batch.pick(quantity=1)

    batches = list_depleted_batches()

    assert [batch.batch_id for batch in batches] == ["A-002"]

    active_batch.refresh_from_db()
    depleted_batch.refresh_from_db()

    assert active_batch.status == InventoryBatch.Status.ACTIVE
    assert depleted_batch.status == InventoryBatch.Status.DEPLETED


@pytest.mark.django_db
def test_list_expiring_batch_rows_for_dashboard_limits_rows(apple, batch_factory):
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
        best_before=TODAY + timedelta(days=1),
        location="Shelf A1",
    )
    batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=10,
        best_before=TODAY + timedelta(days=2),
        location="Shelf A2",
    )
    batch_factory(
        product=apple,
        batch_id="A-003",
        quantity=10,
        best_before=TODAY + timedelta(days=3),
        location="Shelf A3",
    )

    rows = list_expiring_batch_rows_for_dashboard(limit=2, today=TODAY)

    assert [row.batch.batch_id for row in rows] == ["A-001", "A-002"]


@pytest.mark.django_db
def test_count_expiring_batches_counts_active_available_batches(apple, batch_factory):
    active = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
        best_before=TODAY + timedelta(days=EXPIRY_SOON_DAYS),
    )
    depleted = batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=1,
        best_before=TODAY + timedelta(days=EXPIRY_SOON_DAYS),
        location="Shelf A2",
    )
    depleted.pick(quantity=1)
    closed = batch_factory(
        product=apple,
        batch_id="A-003",
        quantity=10,
        best_before=TODAY + timedelta(days=EXPIRY_SOON_DAYS),
        location="Shelf A3",
    )
    closed.close()

    assert count_expiring_batches(today=TODAY) == 1

    active.refresh_from_db()
    assert active.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_list_low_stock_products_for_dashboard_returns_low_stock_rows(
    apple,
    banana,
    batch_factory,
):
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=5,
    )
    batch_factory(
        product=banana,
        batch_id="B-001",
        quantity=20,
        best_before=TODAY + timedelta(days=75),
        location="Shelf B1",
    )

    rows = list_low_stock_products_for_dashboard(threshold=10, limit=3)

    assert [row.sku for row in rows] == ["GENERIC-APPLE-5000"]


@pytest.mark.django_db
def test_count_low_stock_products_counts_low_stock_rows(
    apple,
    banana,
    batch_factory,
):
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=5,
    )
    batch_factory(
        product=banana,
        batch_id="B-001",
        quantity=20,
        best_before=TODAY + timedelta(days=75),
        location="Shelf B1",
    )

    assert count_low_stock_products(threshold=10) == 1
