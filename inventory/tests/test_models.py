from __future__ import annotations

from datetime import timedelta

import pytest

from inventory.errors import (
    InvalidBatchStatusTransition,
    InvalidStockOperation,
)
from inventory.models import InventoryBatch, normalize_batch_id, normalize_location
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
        quantity=10,
        best_before=TODAY + timedelta(days=60),
        location="  Shelf   A1 ",
    )

    assert batch.batch_id == "A-001"
    assert batch.location == "Shelf A1"


@pytest.mark.django_db
def test_new_batch_with_positive_quantity_is_active_and_available(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_pick_reduces_quantity_and_keeps_batch_active_when_quantity_remains(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    batch.pick(quantity=1)
    batch.refresh_from_db()

    assert batch.quantity == 2
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_pick_depletes_batch_when_last_unit_is_removed(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    batch.pick(quantity=3)
    batch.refresh_from_db()

    assert batch.quantity == 0
    assert batch.status == InventoryBatch.Status.DEPLETED
    assert batch.is_available is False


@pytest.mark.django_db
def test_pick_rejects_non_positive_quantity(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    with pytest.raises(InvalidStockOperation, match="quantity must be positive"):
        batch.pick(quantity=0)


@pytest.mark.django_db
def test_pick_rejects_more_quantity_than_available(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    with pytest.raises(InvalidStockOperation, match="Cannot remove 4 units"):
        batch.pick(quantity=4)


@pytest.mark.django_db
def test_adjust_quantity_sets_absolute_physical_count(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    batch.adjust_quantity(quantity=10)
    batch.refresh_from_db()

    assert batch.quantity == 10
    assert batch.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_adjust_quantity_can_deplete_batch(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    batch.adjust_quantity(quantity=0)
    batch.refresh_from_db()

    assert batch.quantity == 0
    assert batch.status == InventoryBatch.Status.DEPLETED
    assert batch.is_available is False


@pytest.mark.django_db
def test_adjust_quantity_can_reactivate_depleted_batch(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=1,
    )

    batch.pick(quantity=1)
    batch.refresh_from_db()

    assert batch.status == InventoryBatch.Status.DEPLETED

    batch.adjust_quantity(quantity=5)
    batch.refresh_from_db()

    assert batch.quantity == 5
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_adjust_quantity_rejects_negative_count(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=3,
    )

    with pytest.raises(InvalidStockOperation, match="quantity must be non-negative"):
        batch.adjust_quantity(quantity=-1)


@pytest.mark.django_db
def test_close_marks_batch_closed_without_changing_quantity(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    batch.close()
    batch.refresh_from_db()

    assert batch.quantity == 10
    assert batch.status == InventoryBatch.Status.CLOSED
    assert batch.is_available is False


@pytest.mark.django_db
def test_closed_batch_cannot_be_picked_or_adjusted(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    batch.close()
    batch.refresh_from_db()

    with pytest.raises(InvalidStockOperation, match="not available"):
        batch.pick(quantity=1)

    with pytest.raises(InvalidStockOperation, match="is closed"):
        batch.adjust_quantity(quantity=20)


@pytest.mark.django_db
def test_closed_batch_cannot_be_reopened_by_saving_positive_quantity(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    batch.close()
    batch.quantity = 20
    batch.save(update_fields=["quantity"])
    batch.refresh_from_db()

    assert batch.quantity == 20
    assert batch.status == InventoryBatch.Status.CLOSED


@pytest.mark.django_db
def test_closed_batch_cannot_transition_back_to_active(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    batch.close()

    with pytest.raises(InvalidBatchStatusTransition, match="Cannot transition"):
        batch.status = InventoryBatch.Status.ACTIVE
        batch.save(update_fields=["status"])


@pytest.mark.django_db
def test_batch_string_contains_batch_product_and_quantity(apple, batch_factory):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    assert str(batch) == f"A-001 - {apple.display_name} (10 boxes)"
