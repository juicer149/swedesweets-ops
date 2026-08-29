from __future__ import annotations

from collections.abc import Iterable, Mapping

from reservations.protocols import (
    BatchAvailability,
    BatchPick,
)


class InvalidReservationPlan(ValueError):
    """Raised when reservation planner input violates its contract."""


class InsufficientReservationCapacity(ValueError):
    """Raised when a supplied batch pool cannot satisfy a request."""

    def __init__(
        self,
        *,
        requested_quantity: int,
        available_quantity: int,
    ) -> None:
        self.requested_quantity = requested_quantity
        self.available_quantity = available_quantity
        self.missing_quantity = max(
            requested_quantity - available_quantity,
            0,
        )

        super().__init__(
            "insufficient reservation capacity"
        )


def plan_batch_picks(
    *,
    batches: Iterable[BatchAvailability],
    requested_quantity: int,
    reserved_quantity_by_batch_pk: Mapping[int, int],
) -> list[BatchPick]:
    """Plan FEFO picks from one homogeneous product batch pool.

    The function is deliberately pure:

    - no database access
    - no locking
    - no model mutation
    - no mutation of input mappings
    - no knowledge of retail or business channels
    """

    if requested_quantity <= 0:
        raise InvalidReservationPlan(
            "requested quantity must be positive"
        )

    pool = list(batches)

    if not pool:
        raise InsufficientReservationCapacity(
            requested_quantity=requested_quantity,
            available_quantity=0,
        )

    product_ids = {
        batch.product_id
        for batch in pool
    }

    if len(product_ids) != 1:
        raise InvalidReservationPlan(
            "batch pool must contain exactly one product"
        )

    for batch in pool:
        if batch.physical_quantity < 0:
            raise InvalidReservationPlan(
                "physical quantity must not be negative"
            )

    for quantity in reserved_quantity_by_batch_pk.values():
        if quantity < 0:
            raise InvalidReservationPlan(
                "reserved quantity must not be negative"
            )

    ordered_batches = sorted(
        pool,
        key=lambda batch: (
            batch.best_before,
            batch.batch_code,
            batch.batch_pk,
        ),
    )

    remaining_quantity = requested_quantity
    total_available_quantity = 0
    picks: list[BatchPick] = []

    for batch in ordered_batches:
        reserved_quantity = (
            reserved_quantity_by_batch_pk.get(
                batch.batch_pk,
                0,
            )
        )

        allocatable_quantity = max(
            batch.physical_quantity - reserved_quantity,
            0,
        )

        total_available_quantity += allocatable_quantity

        if allocatable_quantity == 0:
            continue

        quantity_to_pick = min(
            allocatable_quantity,
            remaining_quantity,
        )

        picks.append(
            BatchPick(
                batch_pk=batch.batch_pk,
                quantity=quantity_to_pick,
            )
        )

        remaining_quantity -= quantity_to_pick

        if remaining_quantity == 0:
            return picks

    raise InsufficientReservationCapacity(
        requested_quantity=requested_quantity,
        available_quantity=total_available_quantity,
    )
