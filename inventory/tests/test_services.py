from __future__ import annotations

from datetime import timedelta

import pytest

from inventory.errors import InvalidStockOperation
from inventory.models import InventoryBatch
from inventory.services import (
    close_batch,
    create_batch,
    update_batch,
)
from inventory.tests.conftest import TODAY


@pytest.mark.django_db
def test_create_batch_with_manual_batch_id_normalizes_fields(
    apple,
):
    batch = create_batch(
        batch_id=" a-001 ",
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="   Shelf   A1   ",
        today=TODAY,
    )

    assert batch.batch_id == "A-001"
    assert batch.location == "Shelf A1"
    assert batch.quantity == 10
    assert batch.status == InventoryBatch.Status.ACTIVE
    assert batch.is_available is True


@pytest.mark.django_db
def test_create_batch_generates_product_based_batch_id_when_missing(
    apple,
):
    first = create_batch(
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )
    second = create_batch(
        product=apple,
        quantity=20,
        best_before=(
            TODAY + timedelta(days=90)
        ),
        location="Shelf A2",
        today=TODAY,
    )

    assert first.batch_id == "PX-GEN-APP-001"
    assert second.batch_id == "PX-GEN-APP-002"


@pytest.mark.django_db
def test_create_batch_generates_internal_number_based_batch_id(
    apple,
):
    apple.internal_number = 7
    apple.save(
        update_fields=["internal_number"],
    )

    batch = create_batch(
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )

    assert batch.batch_id == "P007-GEN-APP-001"


@pytest.mark.django_db
def test_create_batch_generates_separate_sequences_per_product(
    apple,
    banana,
):
    apple.internal_number = 1
    apple.save(
        update_fields=["internal_number"],
    )

    banana.internal_number = 2
    banana.save(
        update_fields=["internal_number"],
    )

    first_apple_batch = create_batch(
        product=apple,
        quantity=10,
        best_before=(
            TODAY + timedelta(days=60)
        ),
        location="Shelf A1",
        today=TODAY,
    )
    first_banana_batch = create_batch(
        product=banana,
        quantity=20,
        best_before=(
            TODAY + timedelta(days=90)
        ),
        location="Shelf B1",
        today=TODAY,
    )
    second_apple_batch = create_batch(
        product=apple,
        quantity=30,
        best_before=(
            TODAY + timedelta(days=120)
        ),
        location="Shelf A2",
        today=TODAY,
    )

    assert (
        first_apple_batch.batch_id
        == "P001-GEN-APP-001"
    )
    assert (
        first_banana_batch.batch_id
        == "P002-GEN-BAN-001"
    )
    assert (
        second_apple_batch.batch_id
        == "P001-GEN-APP-002"
    )


@pytest.mark.django_db
def test_create_batch_rejects_empty_initial_stock(
    apple,
):
    with pytest.raises(
        InvalidStockOperation,
        match="quantity must be positive",
    ):
        create_batch(
            product=apple,
            quantity=0,
            best_before=(
                TODAY + timedelta(days=60)
            ),
            location="Shelf A1",
            today=TODAY,
        )


@pytest.mark.django_db
def test_create_batch_rejects_past_best_before_date(
    apple,
):
    with pytest.raises(
        InvalidStockOperation,
        match="best_before date must be in the future",
    ):
        create_batch(
            product=apple,
            quantity=10,
            best_before=(
                TODAY - timedelta(days=1)
            ),
            location="Shelf A1",
            today=TODAY,
        )


@pytest.mark.django_db
def test_create_batch_rejects_today_as_best_before_date(
    apple,
):
    with pytest.raises(
        InvalidStockOperation,
        match="best_before date must be in the future",
    ):
        create_batch(
            product=apple,
            quantity=10,
            best_before=TODAY,
            location="Shelf A1",
            today=TODAY,
        )


@pytest.mark.django_db
def test_create_batch_allows_non_future_best_before_for_imports(
    apple,
):
    batch = create_batch(
        product=apple,
        quantity=10,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )

    assert batch.best_before == TODAY
    assert batch.quantity == 10
    assert batch.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_create_batch_rejects_duplicate_batch_id(
    apple,
    batch_factory,
):
    batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    with pytest.raises(
        InvalidStockOperation,
        match="Batch A-001 already exists",
    ):
        create_batch(
            batch_id=" a-001 ",
            product=apple,
            quantity=5,
            best_before=(
                TODAY + timedelta(days=90)
            ),
            location="Shelf A2",
            today=TODAY,
        )


@pytest.mark.django_db
def test_update_batch_updates_quantity_best_before_and_location(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    updated = update_batch(
        batch=batch,
        quantity=20,
        best_before=(
            TODAY + timedelta(days=120)
        ),
        location="  Shelf   B2  ",
    )

    updated.refresh_from_db()

    assert updated.quantity == 20
    assert (
        updated.best_before
        == TODAY + timedelta(days=120)
    )
    assert updated.location == "Shelf B2"
    assert updated.status == InventoryBatch.Status.ACTIVE


@pytest.mark.django_db
def test_update_batch_can_deplete_batch_when_quantity_is_zero(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    updated = update_batch(
        batch=batch,
        quantity=0,
        best_before=(
            TODAY + timedelta(days=120)
        ),
        location="Shelf B2",
    )

    updated.refresh_from_db()

    assert updated.quantity == 0
    assert (
        updated.status
        == InventoryBatch.Status.DEPLETED
    )


@pytest.mark.django_db
def test_update_batch_rejects_closed_batch(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )
    batch.close()

    with pytest.raises(
        InvalidStockOperation,
        match="Batch A-001 is closed",
    ):
        update_batch(
            batch=batch,
            quantity=20,
            best_before=(
                TODAY + timedelta(days=120)
            ),
            location="Shelf B2",
        )


@pytest.mark.django_db
def test_close_batch_closes_batch_without_changing_quantity(
    apple,
    batch_factory,
):
    batch = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=10,
    )

    closed = close_batch(
        batch=batch,
    )
    closed.refresh_from_db()

    assert closed.quantity == 10
    assert (
        closed.status
        == InventoryBatch.Status.CLOSED
    )
