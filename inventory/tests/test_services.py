from __future__ import annotations

from datetime import date

import pytest

from inventory.errors import InsufficientStockError, InvalidStockOperation
from inventory.models import InventoryBatch
from inventory.services import (
    close_batch,
    create_batch,
    plan_batch_picks,
    reserved_boxes_for_batch,
    update_batch,
)
from inventory.tests.conftest import TODAY


@pytest.mark.django_db
def test_create_batch_with_manual_batch_id_normalizes_fields(apple):
    batch = create_batch(
        batch_id=" a-001 ",
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="   Shelf   A1   ",
        today=TODAY,
    )

    assert batch.batch_id == "A-001"
    assert batch.location == "Shelf A1"
    assert batch.boxes == 10
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_create_batch_generates_product_based_batch_id_when_missing(apple):
    first = create_batch(
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    second = create_batch(
        product=apple,
        boxes=20,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )

    assert first.batch_id == "PX-GEN-APP-001"
    assert second.batch_id == "PX-GEN-APP-002"


@pytest.mark.django_db
def test_create_batch_generates_internal_number_based_batch_id(apple):
    apple.internal_number = 7
    apple.save(update_fields=["internal_number"])

    batch = create_batch(
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )

    assert batch.batch_id == "P007-GEN-APP-001"


@pytest.mark.django_db
def test_create_batch_generates_separate_sequences_per_product(apple, banana):
    apple.internal_number = 1
    apple.save(update_fields=["internal_number"])

    banana.internal_number = 2
    banana.save(update_fields=["internal_number"])

    first_apple_batch = create_batch(
        product=apple,
        boxes=10,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    first_banana_batch = create_batch(
        product=banana,
        boxes=20,
        best_before=date(2026, 7, 1),
        location="Shelf B1",
        today=TODAY,
    )
    second_apple_batch = create_batch(
        product=apple,
        boxes=30,
        best_before=date(2026, 8, 1),
        location="Shelf A2",
        today=TODAY,
    )

    assert first_apple_batch.batch_id == "P001-GEN-APP-001"
    assert first_banana_batch.batch_id == "P002-GEN-BAN-001"
    assert second_apple_batch.batch_id == "P001-GEN-APP-002"


@pytest.mark.django_db
def test_create_batch_rejects_empty_initial_stock(apple):
    with pytest.raises(InvalidStockOperation, match="boxes must be positive"):
        create_batch(
            product=apple,
            boxes=0,
            best_before=date(2026, 6, 1),
            location="Shelf A1",
            today=TODAY,
        )


@pytest.mark.django_db
def test_create_batch_rejects_past_best_before_date(apple):
    with pytest.raises(
        InvalidStockOperation,
        match="best_before date must be in the future",
    ):
        create_batch(
            product=apple,
            boxes=10,
            best_before=date(2026, 5, 13),
            location="Shelf A1",
            today=TODAY,
        )


@pytest.mark.django_db
def test_create_batch_rejects_today_as_best_before_date(apple):
    with pytest.raises(
        InvalidStockOperation,
        match="best_before date must be in the future",
    ):
        create_batch(
            product=apple,
            boxes=10,
            best_before=TODAY,
            location="Shelf A1",
            today=TODAY,
        )


@pytest.mark.django_db
def test_create_batch_allows_non_future_best_before_for_imports(apple):
    batch = create_batch(
        product=apple,
        boxes=10,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )

    assert batch.best_before == TODAY
    assert batch.boxes == 10
    assert batch.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_create_batch_rejects_duplicate_batch_id(apple, batch_factory):
    batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )

    with pytest.raises(InvalidStockOperation, match="Batch A-001 already exists"):
        create_batch(
            batch_id=" a-001 ",
            product=apple,
            boxes=5,
            best_before=date(2026, 7, 1),
            location="Shelf A2",
            today=TODAY,
        )


@pytest.mark.django_db
def test_update_batch_updates_boxes_best_before_and_location(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )

    updated = update_batch(
        batch=batch,
        boxes=20,
        best_before=date(2026, 8, 1),
        location="  Shelf   B2  ",
    )

    updated.refresh_from_db()

    assert updated.boxes == 20
    assert updated.best_before == date(2026, 8, 1)
    assert updated.location == "Shelf B2"
    assert updated.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_update_batch_can_deplete_batch_when_boxes_are_zero(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )

    updated = update_batch(
        batch=batch,
        boxes=0,
        best_before=date(2026, 8, 1),
        location="Shelf B2",
    )

    updated.refresh_from_db()

    assert updated.boxes == 0
    assert updated.status == InventoryBatch.Status.DEPLETED


@pytest.mark.django_db
def test_update_batch_rejects_closed_batch(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )
    batch.close()

    with pytest.raises(InvalidStockOperation, match="Batch A-001 is closed"):
        update_batch(
            batch=batch,
            boxes=20,
            best_before=date(2026, 8, 1),
            location="Shelf B2",
        )


@pytest.mark.django_db
def test_close_batch_closes_batch_without_changing_boxes(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )

    closed = close_batch(batch=batch)
    closed.refresh_from_db()

    assert closed.boxes == 10
    assert closed.status == InventoryBatch.Status.CLOSED


@pytest.mark.django_db
def test_reserved_boxes_for_batch_is_zero_without_allocations(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )

    assert reserved_boxes_for_batch(batch=batch) == 0


@pytest.mark.django_db
def test_plan_batch_picks_uses_fefo_order(apple, batch_factory):
    late = batch_factory(
        product=apple,
        batch_id="A-002",
        boxes=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
    )
    early = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
    )

    picks = plan_batch_picks(
        product=apple,
        boxes=120,
        reserved_boxes_by_batch_id={},
    )

    assert [(pick.batch, pick.boxes) for pick in picks] == [
        (early, 100),
        (late, 20),
    ]


@pytest.mark.django_db
def test_plan_batch_picks_respects_existing_reserved_boxes(apple, batch_factory):
    early = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=100,
    )
    late = batch_factory(
        product=apple,
        batch_id="A-002",
        boxes=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
    )

    picks = plan_batch_picks(
        product=apple,
        boxes=80,
        reserved_boxes_by_batch_id={
            early.id: 30,
        },
    )

    assert [(pick.batch, pick.boxes) for pick in picks] == [
        (early, 70),
        (late, 10),
    ]


@pytest.mark.django_db
def test_plan_batch_picks_mutates_reserved_boxes_mapping_for_later_lines(
    apple,
    batch_factory,
):
    early = batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=100,
    )

    reserved_boxes_by_batch_id: dict[int, int] = {}

    plan_batch_picks(
        product=apple,
        boxes=40,
        reserved_boxes_by_batch_id=reserved_boxes_by_batch_id,
    )

    assert reserved_boxes_by_batch_id == {
        early.id: 40,
    }


@pytest.mark.django_db
def test_plan_batch_picks_rejects_non_positive_request(apple):
    with pytest.raises(InvalidStockOperation, match="boxes must be positive"):
        plan_batch_picks(
            product=apple,
            boxes=0,
            reserved_boxes_by_batch_id={},
        )


@pytest.mark.django_db
def test_plan_batch_picks_raises_when_stock_is_insufficient(apple, batch_factory):
    batch_factory(
        product=apple,
        batch_id="A-001",
        boxes=10,
    )

    with pytest.raises(InsufficientStockError):
        plan_batch_picks(
            product=apple,
            boxes=11,
            reserved_boxes_by_batch_id={},
        )
