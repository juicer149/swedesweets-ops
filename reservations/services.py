from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.db.models import QuerySet

from inventory.models import InventoryBatch
from orders.models import Allocation, OrderLine
from reservations.planning import plan_batch_picks
from reservations.protocols import BatchAvailability
from reservations.selectors import (
    active_reserved_quantities_by_batch_pk,
)


class InvalidReservationPool(ValueError):
    """Raised when supplied batches cannot represent one reservation pool."""


@transaction.atomic
def reserve_order_line_from_pool(
    *,
    order_line: OrderLine,
    batches: QuerySet[InventoryBatch],
    quantity: int,
    reserved_until: datetime | None = None,
) -> list[Allocation]:
    """Reserve an order line from an explicitly selected batch pool.

    The caller owns eligibility policy.

    This service owns:
    - locking the supplied pool
    - reading current physical quantities
    - reading active reservations
    - FEFO planning
    - persisting Allocation rows
    """

    locked_batches = list(
        batches
        .select_for_update()
        .order_by(
            "best_before",
            "batch_id",
            "id",
        )
    )

    _validate_pool(
        order_line=order_line,
        batches=locked_batches,
    )

    batch_pks = [
        batch.pk
        for batch in locked_batches
    ]

    reserved_quantity_by_batch_pk = (
        active_reserved_quantities_by_batch_pk(
            batch_pks=batch_pks,
        )
    )

    planning_batches = [
        BatchAvailability(
            batch_pk=batch.pk,
            batch_code=batch.batch_id,
            product_id=batch.product_id,
            physical_quantity=batch.quantity,
            best_before=batch.best_before,
        )
        for batch in locked_batches
    ]

    picks = plan_batch_picks(
        batches=planning_batches,
        requested_quantity=quantity,
        reserved_quantity_by_batch_pk=(
            reserved_quantity_by_batch_pk
        ),
    )

    batches_by_pk = {
        batch.pk: batch
        for batch in locked_batches
    }

    allocations = [
        Allocation(
            order=order_line.order,
            order_line=order_line,
            batch=batches_by_pk[pick.batch_pk],
            quantity=pick.quantity,
            reserved_until=reserved_until,
        )
        for pick in picks
    ]

    Allocation.objects.bulk_create(
        allocations,
    )

    return allocations


def _validate_pool(
    *,
    order_line: OrderLine,
    batches: list[InventoryBatch],
) -> None:
    """Protect the mechanical reservation boundary.

    Eligibility itself is caller policy, but a reservation pool may never mix
    products or reserve a product different from its order line.
    """

    product_ids = {
        batch.product_id
        for batch in batches
    }

    if len(product_ids) > 1:
        raise InvalidReservationPool(
            "reservation pool must contain one product"
        )

    if product_ids and product_ids != {
        order_line.product_id,
    }:
        raise InvalidReservationPool(
            "reservation pool product does not match order line"
        )
