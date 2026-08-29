from __future__ import annotations

from collections.abc import Iterable

from reservations.aggregation import (
    aggregate_reserved_quantities,
)
from reservations.providers import (
    active_allocation_reservations,
)


def active_reserved_quantities_by_batch_pk(
    *,
    batch_pks: Iterable[int],
) -> dict[int, int]:
    """Return active reserved quantities for requested batches."""

    return aggregate_reserved_quantities(
        batch_pks=batch_pks,
        providers=[
            active_allocation_reservations,
        ],
    )


def active_reserved_quantity_for_batch_pk(
    *,
    batch_pk: int,
) -> int:
    """Return active reserved quantity for one physical batch."""

    return active_reserved_quantities_by_batch_pk(
        batch_pks=[batch_pk],
    ).get(
        batch_pk,
        0,
    )
