from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Q

from inventory.models import InventoryBatch
from orders.models import Allocation, Order
from reservations.aggregation import (
    aggregate_reserved_quantities,
)
from reservations.datatypes import (
    BatchUsage,
    ReservationPick,
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


def has_reservations_for_order(
    *,
    order: Order,
) -> bool:
    """Return whether an order has any allocation records."""

    return Allocation.objects.filter(
        order=order,
    ).exists()


def list_reserved_picks_for_order(
    *,
    order: Order,
) -> list[ReservationPick]:
    """Return currently RESERVED batch picks for an order."""

    allocations = (
        Allocation.objects
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
        )
        .select_related(
            "batch",
            "batch__product",
        )
        .order_by(
            "order_line_id",
            "batch__best_before",
            "batch__batch_id",
        )
    )

    return [
        _build_reservation_pick(
            allocation=allocation,
        )
        for allocation in allocations
    ]


def list_consumed_picks_for_order(
    *,
    order: Order,
) -> list[ReservationPick]:
    """Return consumed batch picks for an order."""

    allocations = (
        Allocation.objects
        .filter(
            order=order,
            status=Allocation.Status.CONSUMED,
        )
        .select_related(
            "batch",
            "batch__product",
        )
        .order_by(
            "order_line_id",
            "batch__best_before",
            "batch__batch_id",
        )
    )

    return [
        _build_reservation_pick(
            allocation=allocation,
        )
        for allocation in allocations
    ]


def list_batch_usage(
    *,
    batch: InventoryBatch,
) -> list[BatchUsage]:
    """Return reservation/allocation usage history for one batch."""

    now = timezone.now()

    allocations = (
        Allocation.objects
        .filter(
            batch=batch,
        )
        .select_related(
            "order",
            "order__customer",
            "order_line",
            "order_line__product",
            "batch__product",
        )
        .order_by(
            "-order__created_at",
            "-id",
        )
    )

    return [
        BatchUsage(
            order=allocation.order,
            buyer_name=allocation.order.buyer_name,
            customer_id=allocation.order.customer_id,
            quantity=allocation.quantity,
            quantity_label=(
                allocation.batch.product.stock_quantity_label(
                    allocation.quantity
                )
            ),
            allocation_status=allocation.get_status_display(),
            order_status=allocation.order.get_status_display(),
            is_active_reservation=(
                allocation.status == Allocation.Status.RESERVED
                and (
                    allocation.reserved_until is None
                    or allocation.reserved_until > now
                )
            ),
        )
        for allocation in allocations
    ]


def _build_reservation_pick(
    *,
    allocation: Allocation,
) -> ReservationPick:
    product = allocation.batch.product

    return ReservationPick(
        sku=product.sku,
        product_name=product.catalog_label,
        batch_code=allocation.batch.batch_id,
        location=allocation.batch.location,
        quantity=allocation.quantity,
        quantity_label=product.stock_quantity_label(
            allocation.quantity
        ),
    )
