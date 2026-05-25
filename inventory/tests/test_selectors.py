from __future__ import annotations

from datetime import date

import pytest

from inventory.models import InventoryBatch
from inventory.selectors import (
    build_expiry_info,
    count_expiring_batches,
    count_low_stock_products,
    list_available_batches,
    list_available_batches_for_product,
    list_batch_rows,
    list_batches,
    list_depleted_batches,
    list_expiring_batch_rows_for_dashboard,
    list_low_stock_products_for_dashboard,
    physical_boxes_by_product,
    available_boxes_by_product,
    available_boxes_by_product_id,
)
from inventory.services import create_batch
from inventory.tests.conftest import TODAY


def test_build_expiry_info_marks_expired_batch():
    expiry = build_expiry_info(
        best_before=date(2026, 5, 13),
        today=TODAY,
    )

    assert expiry.state == "expired"
    assert expiry.label == "Expired"
    assert expiry.days_left == -1


def test_build_expiry_info_marks_batch_expiring_today_as_critical():
    expiry = build_expiry_info(
        best_before=TODAY,
        today=TODAY,
    )

    assert expiry.state == "critical"
    assert expiry.label == "Expires today"
    assert expiry.days_left == 0


def test_build_expiry_info_marks_critical_batch():
    expiry = build_expiry_info(
        best_before=date(2026, 5, 28),
        today=TODAY,
    )

    assert expiry.state == "critical"
    assert expiry.label == "Expires in 14 days"
    assert expiry.days_left == 14


def test_build_expiry_info_marks_soon_batch():
    expiry = build_expiry_info(
        best_before=date(2026, 7, 13),
        today=TODAY,
    )

    assert expiry.state == "soon"
    assert expiry.label == "Expires in 60 days"
    assert expiry.days_left == 60


def test_build_expiry_info_marks_safe_batch():
    expiry = build_expiry_info(
        best_before=date(2026, 7, 14),
        today=TODAY,
    )

    assert expiry.state == "safe"
    assert expiry.label == "Best before"
    assert expiry.days_left == 61


@pytest.mark.django_db
def test_list_batches_defaults_to_best_before_order(apple):
    create_batch(
        batch_id="A-002",
        product=apple,
        boxes=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batches = list(list_batches())

    assert [batch.batch_id for batch in batches] == ["A-001", "A-002"]


@pytest.mark.django_db
def test_list_batches_filters_by_valid_status(apple):
    active_batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    depleted_batch = create_batch(
        batch_id="A-002",
        product=apple,
        boxes=1,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )
    depleted_batch.pick(boxes=1)

    batches = list(list_batches(status=InventoryBatch.Status.DEPLETED))

    assert active_batch not in batches
    assert depleted_batch in batches


@pytest.mark.django_db
def test_list_batch_rows_adds_expiry_info(apple):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 5, 28),
        location="Shelf A1",
        today=TODAY,
    )

    rows = list_batch_rows(today=TODAY)

    assert len(rows) == 1
    assert rows[0].batch.batch_id == "A-001"
    assert rows[0].expiry.state == "critical"


@pytest.mark.django_db
def test_physical_boxes_by_product_sums_only_active_available_batches(
    apple,
    banana,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    depleted = create_batch(
        batch_id="A-002",
        product=apple,
        boxes=1,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )
    depleted.pick(boxes=1)
    create_batch(
        batch_id="B-001",
        product=banana,
        boxes=80,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
        today=TODAY,
    )

    rows = physical_boxes_by_product()
    boxes_by_sku = {row.sku: row.boxes for row in rows}

    assert boxes_by_sku == {
        "GENERIC-APPLE-5000": 100,
        "GENERIC-BANANA-6000": 80,
    }


@pytest.mark.django_db
def test_available_boxes_by_product_matches_physical_stock_without_reservations(
    stocked_inventory,
):
    rows = available_boxes_by_product()
    available_by_sku = {row.sku: row.available_boxes for row in rows}

    assert available_by_sku == {
        "GENERIC-APPLE-5000": 150,
        "GENERIC-BANANA-6000": 80,
    }


@pytest.mark.django_db
def test_available_boxes_by_product_id_returns_mapping(stocked_inventory, apple, banana):
    available = available_boxes_by_product_id()

    assert available == {
        apple.id: 150,
        banana.id: 80,
    }


@pytest.mark.django_db
def test_list_available_batches_for_product_returns_active_batches_in_fefo_order(
    apple,
    banana,
):
    create_batch(
        batch_id="A-002",
        product=apple,
        boxes=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    create_batch(
        batch_id="B-001",
        product=banana,
        boxes=80,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
        today=TODAY,
    )

    batches = list_available_batches_for_product(product=apple)

    assert [batch.batch_id for batch in batches] == ["A-001", "A-002"]


@pytest.mark.django_db
def test_list_available_batches_returns_active_batches_ordered_by_product_and_fefo(
    apple,
    banana,
):
    create_batch(
        batch_id="B-001",
        product=banana,
        boxes=80,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
        today=TODAY,
    )
    create_batch(
        batch_id="A-002",
        product=apple,
        boxes=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batches = list_available_batches()

    assert [(batch.product.sku, batch.batch_id) for batch in batches] == [
        ("GENERIC-APPLE-5000", "A-001"),
        ("GENERIC-APPLE-5000", "A-002"),
        ("GENERIC-BANANA-6000", "B-001"),
    ]


@pytest.mark.django_db
def test_list_depleted_batches_returns_only_depleted_batches(apple):
    active_batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    depleted_batch = create_batch(
        batch_id="A-002",
        product=apple,
        boxes=1,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )

    depleted_batch.pick(boxes=1)

    batches = list_depleted_batches()

    assert [batch.batch_id for batch in batches] == ["A-002"]

    active_batch.refresh_from_db()
    depleted_batch.refresh_from_db()

    assert active_batch.status == InventoryBatch.Status.ACTIVE
    assert depleted_batch.status == InventoryBatch.Status.DEPLETED


@pytest.mark.django_db
def test_list_expiring_batch_rows_for_dashboard_limits_rows(apple):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    create_batch(
        batch_id="A-002",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 2),
        location="Shelf A2",
        today=TODAY,
    )
    create_batch(
        batch_id="A-003",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 3),
        location="Shelf A3",
        today=TODAY,
    )

    rows = list_expiring_batch_rows_for_dashboard(limit=2, today=TODAY)

    assert [row.batch.batch_id for row in rows] == ["A-001", "A-002"]


@pytest.mark.django_db
def test_count_expiring_batches_counts_active_available_batches(apple):
    active = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    depleted = create_batch(
        batch_id="A-002",
        product=apple,
        boxes=1,
        best_before=date(2026, 6, 2),
        location="Shelf A2",
        today=TODAY,
    )
    depleted.pick(boxes=1)
    closed = create_batch(
        batch_id="A-003",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 3),
        location="Shelf A3",
        today=TODAY,
    )
    closed.close()

    assert count_expiring_batches() == 1

    active.refresh_from_db()
    assert active.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_list_low_stock_products_for_dashboard_returns_low_stock_rows(
    apple,
    banana,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=5,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    create_batch(
        batch_id="B-001",
        product=banana,
        boxes=20,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
        today=TODAY,
    )

    rows = list_low_stock_products_for_dashboard(threshold=10, limit=3)

    assert [row.sku for row in rows] == ["GENERIC-APPLE-5000"]


@pytest.mark.django_db
def test_count_low_stock_products_counts_low_stock_rows(apple, banana):
    create_batch(
        batch_id="A-001",
        product=apple,
        boxes=5,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    create_batch(
        batch_id="B-001",
        product=banana,
        boxes=20,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
        today=TODAY,
    )

    assert count_low_stock_products(threshold=10) == 1
