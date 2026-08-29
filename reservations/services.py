from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from django.db import transaction
from django.db.models import QuerySet

from inventory.models import InventoryBatch
from orders.models import Allocation, Order, OrderLine
from reservations.planning import plan_batch_picks
from reservations.protocols import BatchAvailability
from reservations.selectors import (
    active_reserved_quantities_by_batch_pk,
)


class InvalidReservationPool(ValueError):
    """Raised when supplied batches cannot represent one reservation pool."""


class MissingReservations(ValueError):
    """Raised when an operation requires reservations but none exist."""


@transaction.atomic
def reserve_order_line_from_pool(
    *,
    order_line: OrderLine,
    batches: QuerySet[InventoryBatch],
    quantity: int,
    reserved_until: datetime | None = None,
) -> None:
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

    Allocation.objects.bulk_create(
        [
            Allocation(
                order=order_line.order,
                order_line=order_line,
                batch=batches_by_pk[pick.batch_pk],
                quantity=pick.quantity,
                reserved_until=reserved_until,
            )
            for pick in picks
        ]
    )


@transaction.atomic
def cancel_reservations_for_order(
    *,
    order: Order,
) -> None:
    """Cancel every currently RESERVED allocation for an order."""

    allocations = list(
        Allocation.objects
        .select_for_update()
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
        )
        .order_by("id")
    )

    for allocation in allocations:
        allocation.cancel()


@transaction.atomic
def cancel_temporary_reservations_for_order(
    *,
    order: Order,
) -> None:
    """Cancel temporary reservations for an order.

    Non-expiring reservations are deliberately left untouched.
    """

    allocations = list(
        Allocation.objects
        .select_for_update()
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
            reserved_until__isnull=False,
        )
        .order_by("id")
    )

    for allocation in allocations:
        allocation.cancel()


@transaction.atomic
def delete_reservations_for_order(
    *,
    order: Order,
) -> None:
    """Delete RESERVED allocations before rebuilding an order.

    Consumed and cancelled allocation history is deliberately preserved.
    """

    (
        Allocation.objects
        .select_for_update()
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
        )
        .delete()
    )


@transaction.atomic
def consume_reservations_for_order(
    *,
    order: Order,
) -> None:
    """Consume reservations and reduce the corresponding physical stock.

    Allocation rows and physical inventory batches are locked before mutation.
    The physical pick and reservation state transitions therefore happen in the
    same database transaction.
    """

    allocations = list(
        Allocation.objects
        .select_related("batch")
        .select_for_update()
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
        )
        .order_by(
            "batch__best_before",
            "batch__batch_id",
            "id",
        )
    )

    if not allocations:
        raise MissingReservations(
            f"order {order.pk} has no reserved allocations"
        )

    quantity_by_batch_pk: dict[int, int] = defaultdict(int)

    for allocation in allocations:
        quantity_by_batch_pk[
            allocation.batch_id
        ] += allocation.quantity

    locked_batches = {
        batch.pk: batch
        for batch in (
            InventoryBatch.objects
            .select_for_update()
            .filter(
                pk__in=quantity_by_batch_pk,
            )
            .order_by("pk")
        )
    }

    for batch_pk, quantity in quantity_by_batch_pk.items():
        batch = locked_batches[
            batch_pk
        ]

        batch.pick(
            quantity=quantity,
        )

    for allocation in allocations:
        allocation.consume()


def _validate_pool(
    *,
    order_line: OrderLine,
    batches: list[InventoryBatch],
) -> None:
    """Protect the mechanical reservation boundary.

    Eligibility itself belongs to the caller's policy, but one reservation
    pool may not mix products or target a product different from the order line.
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
