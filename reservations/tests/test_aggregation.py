from __future__ import annotations

import pytest

from reservations.aggregation import (
    aggregate_reserved_quantities,
)


def test_aggregate_reserved_quantities_returns_empty_for_no_batches():
    result = aggregate_reserved_quantities(
        batch_pks=[],
        providers=[],
    )

    assert result == {}


def test_aggregate_reserved_quantities_combines_multiple_providers():
    def first_provider(*, batch_pks):
        assert batch_pks == (1, 2)
        return [
            (1, 3),
            (2, 4),
        ]

    def second_provider(*, batch_pks):
        assert batch_pks == (1, 2)
        return [
            (1, 2),
        ]

    result = aggregate_reserved_quantities(
        batch_pks=[1, 2],
        providers=[
            first_provider,
            second_provider,
        ],
    )

    assert result == {
        1: 5,
        2: 4,
    }


def test_aggregate_reserved_quantities_ignores_unrequested_batches():
    def provider(*, batch_pks):
        return [
            (1, 3),
            (999, 100),
        ]

    result = aggregate_reserved_quantities(
        batch_pks=[1],
        providers=[provider],
    )

    assert result == {
        1: 3,
    }


def test_aggregate_reserved_quantities_rejects_negative_quantity():
    def provider(*, batch_pks):
        return [
            (1, -1),
        ]

    with pytest.raises(
        ValueError,
        match="must not be negative",
    ):
        aggregate_reserved_quantities(
            batch_pks=[1],
            providers=[provider],
        )
