"""
Order application services.

These functions coordinate order use-cases. This module is allowed to orchestrate
customers, products and inventory, but it should not duplicate customer, product
or inventory rules.

The service layer owns use-case transactions:
    - create draft order
    - place order / reserve inventory
    - update placed order / rebuild reservations
    - pack order / consume reservations and pick physical stock
    - cancel order / release reservations
    - deliver order

UI/HTTP code should call this module instead of mutating Order, OrderLine or
Allocation directly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone

from customers.models import Customer
from inventory.models import InventoryBatch
from inventory.services import plan_batch_picks
from orders.datatypes import OrderLineInput
from orders.errors import InvalidOrderOperation
from orders.models import Allocation, Order, OrderLine
from products.models import Product
from products.units import normalize_order_unit, quantity_to_units


@dataclass(frozen=True)
class NormalizedOrderLine:
    """Order line normalized to the operational fulfillment unit.

    External input may use stock units, kg, or grams. The order workflow reserves
    and picks stock in whole product stock units.
    """

    product: Product
    quantity: int


@transaction.atomic
def create_draft_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
) -> Order:
    """Create an order in DRAFT status.

    Multiple input lines for the same product are normalized to stock units and
    merged into one OrderLine.
    """

    return _create_draft_order(
        customer=customer,
        lines=lines,
    )


@transaction.atomic
def get_or_create_customer_draft_order(
    *,
    customer: Customer,
) -> Order:
    """Return the customer's active draft order, creating one if needed.

    A customer may have at most one active draft. The database constraint owns
    that invariant; this service provides the application-level workflow.
    """

    draft = (
        Order.objects
        .select_for_update()
        .filter(
            customer=customer,
            status=Order.Status.DRAFT,
        )
        .order_by("created_at", "id")
        .first()
    )

    if draft is not None:
        return draft

    order = Order(customer=customer)
    order.snapshot_customer()

    try:
        with transaction.atomic():
            order.save()
    except IntegrityError:
        return (
            Order.objects
            .select_for_update()
            .get(
                customer=customer,
                status=Order.Status.DRAFT,
            )
        )

    return order


@transaction.atomic
def replace_draft_order_lines(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace all lines on a draft order.

    Draft orders do not reserve stock. Stock is checked and reserved only when
    the order is placed.
    """

    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            f"Only draft orders can be edited; current status is {order.status}"
        )

    normalized_lines = _normalize_order_lines(lines=lines)

    order.lines.all().delete()

    if normalized_lines:
        _create_order_lines(
            order=order,
            normalized_lines=normalized_lines,
        )

    order.updated_at = timezone.now()
    order.save(update_fields=["updated_at"])

    return order


@transaction.atomic
def discard_draft_order(
    *,
    order: Order,
) -> None:
    """Delete an unplaced draft order.

    Draft orders are customer work-in-progress. They do not reserve inventory and
    are safe to delete as long as they have not entered the real order lifecycle.
    """

    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            f"Only draft orders can be discarded; current status is {order.status}"
        )

    if order.allocations.exists():
        raise InvalidOrderOperation(
            f"Cannot discard draft order {order.pk}; it has allocations"
        )

    order.delete()


@transaction.atomic
def create_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Create a draft order and immediately place it."""

    order = _create_draft_order(
        customer=customer,
        lines=lines,
    )

    return _place_order(order=order, user=user)


@transaction.atomic
def place_order(*, order: Order, user=None) -> Order:
    """Reserve inventory batches and move order to PLACED."""

    return _place_order(order=order, user=user)


@transaction.atomic
def update_placed_order(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace lines for a PLACED order and rebuild reservations.

    This is allowed only before physical stock has been picked. The old reserved
    allocations and order lines are deleted, then new normalized lines and
    allocations are created.

    PACKED and DELIVERED orders must use separate workflows such as returns or
    inventory corrections.
    """

    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status != Order.Status.PLACED:
        raise InvalidOrderOperation(
            f"Only placed orders can be edited; current status is {order.status}"
        )

    normalized_lines = _normalize_order_lines(lines=lines)

    if not normalized_lines:
        raise InvalidOrderOperation("order must contain at least one line")

    _delete_reserved_allocations(order=order)
    order.lines.all().delete()

    _create_order_lines(
        order=order,
        normalized_lines=normalized_lines,
    )
    _reserve_order(order=order)
    order.mark_as_edited(user=user)

    return order


@transaction.atomic
def pack_order(*, order: Order, user=None) -> Order:
    """Pick physical inventory and move order to PACKED."""

    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status != Order.Status.PLACED:
        raise InvalidOrderOperation(
            f"Cannot pack order {order.pk}; current status is {order.status}"
        )

    allocations = list(
        order.allocations
        .select_related("batch")
        .select_for_update()
        .filter(status=Allocation.Status.RESERVED)
        .order_by("batch__best_before", "batch__batch_id", "id")
    )

    if not allocations:
        raise InvalidOrderOperation(f"Order {order.pk} has no reserved allocations")

    quantity_by_batch_id: dict[int, int] = defaultdict(int)

    for allocation in allocations:
        quantity_by_batch_id[allocation.batch_id] += allocation.quantity

    locked_batches = {
        batch.id: batch
        for batch in (
            InventoryBatch.objects
            .select_for_update()
            .filter(id__in=quantity_by_batch_id.keys())
            .order_by("id")
        )
    }

    for batch_id, quantity_to_pick in quantity_by_batch_id.items():
        batch = locked_batches[batch_id]
        batch.pick(quantity=quantity_to_pick)

    for allocation in allocations:
        allocation.consume()

    order.mark_as_packed(user=user)

    return order


@transaction.atomic
def cancel_order(
    *,
    order: Order,
    user=None,
    reason: str = "",
    note: str = "",
) -> Order:
    """Cancel order and release reserved allocations."""

    order = Order.objects.select_for_update().get(pk=order.pk)

    if not order.can_be_cancelled:
        raise InvalidOrderOperation(
            f"Cannot cancel order {order.pk}; current status is {order.status}"
        )

    _cancel_reserved_allocations(order=order)
    order.cancel(
        user=user,
        reason=reason,
        note=note,
    )

    return order


@transaction.atomic
def deliver_order(*, order: Order, user=None) -> Order:
    """Move packed order to DELIVERED."""

    order = Order.objects.select_for_update().get(pk=order.pk)
    order.mark_as_delivered(user=user)

    return order


def _create_draft_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
) -> Order:
    normalized_lines = _normalize_order_lines(lines=lines)

    if not normalized_lines:
        raise InvalidOrderOperation("order must contain at least one line")

    order = Order(customer=customer)
    order.snapshot_customer()
    order.save()

    _create_order_lines(
        order=order,
        normalized_lines=normalized_lines,
    )

    return order


def _create_order_lines(
    *,
    order: Order,
    normalized_lines: Iterable[NormalizedOrderLine],
) -> None:
    OrderLine.objects.bulk_create(
        [
            OrderLine(
                order=order,
                product=line.product,
                quantity=line.quantity,
                unit=OrderLine.Unit.STOCK_UNIT,
                quantity_in_units=line.quantity,
            )
            for line in normalized_lines
        ]
    )


def _normalize_order_lines(
    *,
    lines: Iterable[OrderLineInput],
) -> list[NormalizedOrderLine]:
    """Normalize input lines to stock units and merge duplicate products.

    The database should contain one OrderLine per product per order. This function
    enforces that rule in the service layer before the unique database constraint
    acts as the final safety net.
    """

    line_inputs = list(lines)

    if not line_inputs:
        return []

    quantity_by_product_id: dict[int, int] = defaultdict(int)
    products_by_id: dict[int, Product] = {}

    for line_input in line_inputs:
        product = Product.objects.get(pk=line_input.resolve_product_id())
        unit = normalize_order_unit(str(line_input.unit))

        quantity = quantity_to_units(
            product=product,
            quantity=line_input.quantity,
            unit=unit,
        )

        if quantity <= 0:
            raise InvalidOrderOperation("order line quantity must be positive")

        quantity_by_product_id[product.id] += quantity
        products_by_id[product.id] = product

    return [
        NormalizedOrderLine(
            product=products_by_id[product_id],
            quantity=quantity,
        )
        for product_id, quantity in quantity_by_product_id.items()
    ]


def _place_order(*, order: Order, user=None) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            f"Only draft orders can be placed; current status is {order.status}"
        )

    _reserve_order(order=order)
    order.mark_as_placed(user=user)

    return order


def _reserve_order(*, order: Order) -> None:
    lines = list(
        order.lines
        .select_related("product")
        .order_by("id")
    )

    if not lines:
        raise InvalidOrderOperation("order must contain at least one line")

    reserved_quantity_by_batch_id: dict[int, int] = {}
    new_allocations: list[Allocation] = []

    for line in lines:
        _load_existing_reservations_for_line(
            line=line,
            reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
        )

        picks = plan_batch_picks(
            product=line.product,
            quantity=line.quantity_in_units,
            reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
        )

        for pick in picks:
            new_allocations.append(
                Allocation(
                    order=order,
                    order_line=line,
                    batch=pick.batch,
                    quantity=pick.quantity,
                )
            )

    Allocation.objects.bulk_create(new_allocations)


def _load_existing_reservations_for_line(
    *,
    line: OrderLine,
    reserved_quantity_by_batch_id: dict[int, int],
) -> None:
    """Load existing reserved quantity for candidate batches.

    Candidate batches are locked before reading existing reservations. This makes
    reservation planning safer under concurrent order placement.
    """

    candidate_batch_ids = list(
        InventoryBatch.objects
        .select_for_update()
        .filter(
            product=line.product,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
        )
        .values_list("id", flat=True)
    )

    missing_batch_ids = [
        batch_id
        for batch_id in candidate_batch_ids
        if batch_id not in reserved_quantity_by_batch_id
    ]

    if not missing_batch_ids:
        return

    reserved_quantity_by_batch_id.update(
        _reserved_quantity_by_batch_id(batch_ids=missing_batch_ids)
    )


def _reserved_quantity_by_batch_id(
    *,
    batch_ids: Iterable[int] | None = None,
) -> dict[int, int]:
    query = Allocation.objects.filter(
        status=Allocation.Status.RESERVED,
        order__status=Order.Status.PLACED,
    )

    if batch_ids is not None:
        batch_ids = list(batch_ids)

        if not batch_ids:
            return {}

        query = query.filter(batch_id__in=batch_ids)

    rows = (
        query
        .values("batch_id")
        .annotate(total=Sum("quantity"))
    )

    return {
        row["batch_id"]: row["total"] or 0
        for row in rows
    }


def _cancel_reserved_allocations(*, order: Order) -> None:
    allocations = list(
        order.allocations
        .select_for_update()
        .filter(status=Allocation.Status.RESERVED)
    )

    for allocation in allocations:
        allocation.cancel()


def _delete_reserved_allocations(*, order: Order) -> None:
    order.allocations.filter(
        status=Allocation.Status.RESERVED,
    ).delete()
