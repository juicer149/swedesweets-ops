from __future__ import annotations

from datetime import date

import pytest

from reservations.planning import (
    InsufficientReservationCapacity,
    InvalidReservationPlan,
    plan_batch_picks,
)
from reservations.protocols import BatchAvailability


def batch(
    *,
    batch_pk: int,
    batch_code: str,
    product_id: int = 1,
    quantity: int,
    best_before: date,
) -> BatchAvailability:
    return BatchAvailability(
        batch_pk=batch_pk,
        batch_code=batch_code,
        product_id=product_id,
        physical_quantity=quantity,
        best_before=best_before,
    )


def test_plan_batch_picks_uses_fefo():
    early = batch(
        batch_pk=1,
        batch_code="A-001",
        quantity=100,
        best_before=date(2026, 10, 1),
    )
    late = batch(
        batch_pk=2,
        batch_code="A-002",
        quantity=50,
        best_before=date(2026, 11, 1),
    )

    picks = plan_batch_picks(
        batches=[
            late,
            early,
        ],
        requested_quantity=120,
        reserved_quantity_by_batch_pk={},
    )

    assert [
        (pick.batch_pk, pick.quantity)
        for pick in picks
    ] == [
        (1, 100),
        (2, 20),
    ]


def test_plan_batch_picks_respects_existing_reservations():
    early = batch(
        batch_pk=1,
        batch_code="A-001",
        quantity=100,
        best_before=date(2026, 10, 1),
    )
    late = batch(
        batch_pk=2,
        batch_code="A-002",
        quantity=50,
        best_before=date(2026, 11, 1),
    )

    picks = plan_batch_picks(
        batches=[
            early,
            late,
        ],
        requested_quantity=80,
        reserved_quantity_by_batch_pk={
            1: 30,
        },
    )

    assert [
        (pick.batch_pk, pick.quantity)
        for pick in picks
    ] == [
        (1, 70),
        (2, 10),
    ]


def test_plan_batch_picks_does_not_mutate_reservation_input():
    reserved = {
        1: 30,
    }

    plan_batch_picks(
        batches=[
            batch(
                batch_pk=1,
                batch_code="A-001",
                quantity=100,
                best_before=date(2026, 10, 1),
            ),
        ],
        requested_quantity=40,
        reserved_quantity_by_batch_pk=reserved,
    )

    assert reserved == {
        1: 30,
    }


def test_plan_batch_picks_rejects_non_positive_request():
    with pytest.raises(
        InvalidReservationPlan,
        match="must be positive",
    ):
        plan_batch_picks(
            batches=[],
            requested_quantity=0,
            reserved_quantity_by_batch_pk={},
        )


def test_plan_batch_picks_rejects_mixed_product_pool():
    with pytest.raises(
        InvalidReservationPlan,
        match="one product",
    ):
        plan_batch_picks(
            batches=[
                batch(
                    batch_pk=1,
                    batch_code="A-001",
                    product_id=1,
                    quantity=10,
                    best_before=date(2026, 10, 1),
                ),
                batch(
                    batch_pk=2,
                    batch_code="B-001",
                    product_id=2,
                    quantity=10,
                    best_before=date(2026, 10, 1),
                ),
            ],
            requested_quantity=1,
            reserved_quantity_by_batch_pk={},
        )


def test_plan_batch_picks_raises_when_pool_is_empty():
    with pytest.raises(
        InsufficientReservationCapacity,
    ) as error:
        plan_batch_picks(
            batches=[],
            requested_quantity=4,
            reserved_quantity_by_batch_pk={},
        )

    assert error.value.requested_quantity == 4
    assert error.value.available_quantity == 0
    assert error.value.missing_quantity == 4


def test_plan_batch_picks_reports_insufficient_capacity():
    with pytest.raises(
        InsufficientReservationCapacity,
    ) as error:
        plan_batch_picks(
            batches=[
                batch(
                    batch_pk=1,
                    batch_code="A-001",
                    quantity=10,
                    best_before=date(2026, 10, 1),
                ),
            ],
            requested_quantity=12,
            reserved_quantity_by_batch_pk={
                1: 3,
            },
        )

    assert error.value.requested_quantity == 12
    assert error.value.available_quantity == 7
    assert error.value.missing_quantity == 5


def test_plan_batch_picks_uses_batch_code_as_fefo_tie_breaker():
    second = batch(
        batch_pk=1,
        batch_code="A-002",
        quantity=10,
        best_before=date(2026, 10, 1),
    )
    first = batch(
        batch_pk=2,
        batch_code="A-001",
        quantity=10,
        best_before=date(2026, 10, 1),
    )

    picks = plan_batch_picks(
        batches=[
            second,
            first,
        ],
        requested_quantity=12,
        reserved_quantity_by_batch_pk={},
    )

    assert [
        (pick.batch_pk, pick.quantity)
        for pick in picks
    ] == [
        (2, 10),
        (1, 2),
    ]
