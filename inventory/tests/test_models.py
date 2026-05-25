from __future__ import annotations

from datetime import date

import pytest

from inventory.errors import (
    InvalidBatchStatusTransition,
    InvalidStockOperation,
)
from inventory.models import InventoryBatch, normalize_batch_id, normalize_location
from inventory.services import create_batch
from inventory.tests.conftest import TODAY


def test_normalize_batch_id_strips_and_uppercases():
    assert normalize_batch_id("  a-001  ") == "A-001"


def test_normalize_batch_id_rejects_empty_value():
    with pytest.raises(InvalidStockOperation, match="batch id must not be empty"):
        normalize_batch_id("   ")


def test_normalize_location_strips_and_collapses_whitespace():
    assert normalize_location("  Shelf   A1  ") == "Shelf A1"


def test_normalize_location_rejects_empty_value():
    with pytest.raises(InvalidStockOperation, match="location must not be empty"):
        normalize_location("   ")


@pytest.mark.django_db
def test_batch_save_normalizes_batch_id_and_location(apple):
    batch = InventoryBatch.objects.create(
        batch_id="  a-001 ",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="  Shelf   A1 ",
    )

    assert batch.batch_id == "A-001"
    assert batch.location == "Shelf A1"


@pytest.mark.django_db
def test_new_batch_with_positive_boxes_is_active_and_available(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_pick_reduces_boxes_and_keeps_batch_active_when_boxes_remain(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.pick(boxes=1)
    batch.refresh_from_db()

    assert batch.boxes == 2
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_pick_depletes_batch_when_last_box_is_removed(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.pick(boxes=3)
    batch.refresh_from_db()

    assert batch.boxes == 0
    assert batch.status == InventoryBatch.Status.DEPLETED
    assert batch.is_available is False


@pytest.mark.django_db
def test_pick_rejects_non_positive_boxes(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(InvalidStockOperation, match="boxes must be positive"):
        batch.pick(boxes=0)


@pytest.mark.django_db
def test_pick_rejects_more_boxes_than_available(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(InvalidStockOperation, match="Cannot remove 4 boxes"):
        batch.pick(boxes=4)


@pytest.mark.django_db
def test_adjust_boxes_sets_absolute_physical_count(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.adjust_boxes(boxes=10)
    batch.refresh_from_db()

    assert batch.boxes == 10
    assert batch.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_adjust_boxes_can_deplete_batch(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.adjust_boxes(boxes=0)
    batch.refresh_from_db()

    assert batch.boxes == 0
    assert batch.status == InventoryBatch.Status.DEPLETED
    assert batch.is_available is False


@pytest.mark.django_db
def test_adjust_boxes_can_reactivate_depleted_batch(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=1,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.pick(boxes=1)
    batch.refresh_from_db()

    assert batch.status == InventoryBatch.Status.DEPLETED

    batch.adjust_boxes(boxes=5)
    batch.refresh_from_db()

    assert batch.boxes == 5
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_adjust_boxes_rejects_negative_count(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=3,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(InvalidStockOperation, match="boxes must be non-negative"):
        batch.adjust_boxes(boxes=-1)


@pytest.mark.django_db
def test_close_marks_batch_closed_without_changing_box_count(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.close()
    batch.refresh_from_db()

    assert batch.boxes == 10
    assert batch.status == InventoryBatch.Status.CLOSED
    assert batch.is_available is False


@pytest.mark.django_db
def test_closed_batch_cannot_be_picked_or_adjusted(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.close()
    batch.refresh_from_db()

    with pytest.raises(InvalidStockOperation, match="not available"):
        batch.pick(boxes=1)

    with pytest.raises(InvalidStockOperation, match="is closed"):
        batch.adjust_boxes(boxes=20)


@pytest.mark.django_db
def test_closed_batch_cannot_be_reopened_by_saving_positive_boxes(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.close()
    batch.boxes = 20
    batch.save(update_fields=["boxes"])
    batch.refresh_from_db()

    assert batch.boxes == 20
    assert batch.status == InventoryBatch.Status.CLOSED


@pytest.mark.django_db
def test_closed_batch_cannot_transition_back_to_active(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    batch.close()

    with pytest.raises(InvalidBatchStatusTransition, match="Cannot transition"):
        batch.status = InventoryBatch.Status.ACTIVE
        batch.save(update_fields=["status"])


@pytest.mark.django_db
def test_batch_string_contains_batch_product_and_boxes(apple):
    batch = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    assert str(batch) == f"A-001 - {apple.sku} (10 boxes)"
