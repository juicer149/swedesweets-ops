"""
Order application services.

These functions coordinate order use-cases. They may orchestrate customers,
products and inventory, but should not duplicate customer, product or inventory
rules.

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
from collections.abc import Iterable
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from customers.models import Customer
from inventory.errors import InsufficientStockError
from inventory.models import InventoryBatch
from inventory.selectors import (
    list_orderable_batches_for_product,
)
from orders.datatypes import (
    BuyerInput,
    OrderLineInput,
)
from orders.errors import InvalidOrderOperation
from orders.models import (
    Allocation,
    Order,
    OrderLine,
)
from products.models import Product
from products.units import (
    normalize_order_unit,
    quantity_to_units,
)
from reservations.planning import (
    InsufficientReservationCapacity,
)
from reservations.services import (
    reserve_order_line_from_pool,
)


@dataclass(frozen=True)
class NormalizedOrderLine:
    """Order line normalized to the operational fulfillment unit.

    External input may use stock units, kg, or grams. The order workflow
    reserves and picks stock in whole product stock units.
    """

    product: Product
    quantity: int


def buyer_from_customer(
    *,
    customer: Customer,
) -> BuyerInput:
    """Adapt a persisted customer to the buyer contract required by orders."""

    return BuyerInput(
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        country=customer.country,
        city=customer.city,
        address_line=customer.address_line,
        postal_code="",
    )


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
        buyer=buyer_from_customer(
            customer=customer,
        ),
        lines=lines,
    )


@transaction.atomic
def get_or_create_customer_draft_order(
    *,
    customer: Customer,
) -> Order:
    """Return the customer's active draft order, creating one if needed."""

    draft = (
        Order.objects
        .select_for_update()
        .filter(
            customer=customer,
            status=Order.Status.DRAFT,
        )
        .order_by(
            "created_at",
            "id",
        )
        .first()
    )

    if draft is not None:
        return draft

    order = Order(
        customer=customer,
    )
    order.snapshot_buyer(
        buyer=buyer_from_customer(
            customer=customer,
        ),
    )

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

    Draft business orders do not reserve stock. Stock is checked and reserved
    only when the order is placed.
    """

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "Only draft orders can be edited; "
            f"current status is {order.status}"
        )

    normalized_lines = _normalize_order_lines(
        lines=lines,
    )

    order.lines.all().delete()

    if normalized_lines:
        _create_order_lines(
            order=order,
            normalized_lines=normalized_lines,
        )

    order.updated_at = timezone.now()
    order.save(
        update_fields=["updated_at"],
    )

    return order


@transaction.atomic
def discard_draft_order(
    *,
    order: Order,
) -> None:
    """Delete an unplaced draft order."""

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "Only draft orders can be discarded; "
            f"current status is {order.status}"
        )

    if order.allocations.exists():
        raise InvalidOrderOperation(
            f"Cannot discard draft order {order.pk}; "
            "it has allocations"
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
        buyer=buyer_from_customer(
            customer=customer,
        ),
        lines=lines,
    )

    return _place_order(
        order=order,
        user=user,
    )


@transaction.atomic
def place_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Reserve inventory batches and move order to PLACED."""

    return _place_order(
        order=order,
        user=user,
    )


@transaction.atomic
def update_placed_order(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace lines for a PLACED order and rebuild reservations."""

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if order.status != Order.Status.PLACED:
        raise InvalidOrderOperation(
            "Only placed orders can be edited; "
            f"current status is {order.status}"
        )

    normalized_lines = _normalize_order_lines(
        lines=lines,
    )

    if not normalized_lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    _delete_reserved_allocations(
        order=order,
    )
    order.lines.all().delete()

    _create_order_lines(
        order=order,
        normalized_lines=normalized_lines,
    )
    _reserve_order(
        order=order,
    )
    order.mark_as_edited(
        user=user,
    )

    return order


@transaction.atomic
def pack_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Pick physical inventory and move order to PACKED."""

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if order.status != Order.Status.PLACED:
        raise InvalidOrderOperation(
            f"Cannot pack order {order.pk}; "
            f"current status is {order.status}"
        )

    allocations = list(
        order.allocations
        .select_related("batch")
        .select_for_update()
        .filter(
            status=Allocation.Status.RESERVED,
        )
        .order_by(
            "batch__best_before",
            "batch__batch_id",
            "id",
        )
    )

    if not allocations:
        raise InvalidOrderOperation(
            f"Order {order.pk} has no reserved allocations"
        )

    quantity_by_batch_id: dict[int, int] = (
        defaultdict(int)
    )

    for allocation in allocations:
        quantity_by_batch_id[
            allocation.batch_id
        ] += allocation.quantity

    locked_batches = {
        batch.id: batch
        for batch in (
            InventoryBatch.objects
            .select_for_update()
            .filter(
                id__in=quantity_by_batch_id.keys(),
            )
            .order_by("id")
        )
    }

    for batch_id, quantity_to_pick in (
        quantity_by_batch_id.items()
    ):
        batch = locked_batches[
            batch_id
        ]
        batch.pick(
            quantity=quantity_to_pick,
        )

    for allocation in allocations:
        allocation.consume()

    order.mark_as_packed(
        user=user,
    )

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

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if not order.can_be_cancelled:
        raise InvalidOrderOperation(
            f"Cannot cancel order {order.pk}; "
            f"current status is {order.status}"
        )

    _cancel_reserved_allocations(
        order=order,
    )
    order.cancel(
        user=user,
        reason=reason,
        note=note,
    )

    return order


@transaction.atomic
def deliver_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Move packed order to DELIVERED."""

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )
    order.mark_as_delivered(
        user=user,
    )

    return order


def _create_draft_order(
    *,
    customer: Customer,
    buyer: BuyerInput,
    lines: Iterable[OrderLineInput],
) -> Order:
    normalized_lines = _normalize_order_lines(
        lines=lines,
    )

    if not normalized_lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    order = Order(
        customer=customer,
    )
    order.snapshot_buyer(
        buyer=buyer,
    )
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
    line_inputs = list(
        lines,
    )

    if not line_inputs:
        return []

    resolved_inputs = [
        (
            line_input,
            line_input.resolve_product_id(),
        )
        for line_input in line_inputs
    ]

    products_by_id = Product.objects.in_bulk(
        product_id
        for _, product_id in resolved_inputs
    )

    quantity_by_product_id: dict[int, int] = (
        defaultdict(int)
    )

    for line_input, product_id in resolved_inputs:
        try:
            product = products_by_id[
                product_id
            ]
        except KeyError as exc:
            raise InvalidOrderOperation(
                f"Product {product_id} does not exist"
            ) from exc

        unit = normalize_order_unit(
            str(line_input.unit),
        )

        quantity = quantity_to_units(
            product=product,
            quantity=line_input.quantity,
            unit=unit,
        )

        if quantity <= 0:
            raise InvalidOrderOperation(
                "order line quantity must be positive"
            )

        quantity_by_product_id[
            product_id
        ] += quantity

    return [
        NormalizedOrderLine(
            product=products_by_id[
                product_id
            ],
            quantity=quantity,
        )
        for product_id, quantity
        in quantity_by_product_id.items()
    ]


def _place_order(
    *,
    order: Order,
    user=None,
) -> Order:
    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "Only draft orders can be placed; "
            f"current status is {order.status}"
        )

    _reserve_order(
        order=order,
    )
    order.mark_as_placed(
        user=user,
    )

    return order


def _reserve_order(
    *,
    order: Order,
) -> None:
    """Reserve each business order line from normal orderable inventory."""

    lines = list(
        order.lines
        .select_related("product")
        .order_by("id")
    )

    if not lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    for line in lines:
        batches = list_orderable_batches_for_product(
            product=line.product,
        )

        try:
            reserve_order_line_from_pool(
                order_line=line,
                batches=batches,
                quantity=line.quantity_in_units,
                reserved_until=None,
            )
        except InsufficientReservationCapacity as exc:
            raise InsufficientStockError(
                product_name=line.product.display_name,
                requested_quantity=(
                    exc.requested_quantity
                ),
                available_quantity=(
                    exc.available_quantity
                ),
                missing_quantity=(
                    exc.missing_quantity
                ),
            ) from exc


def _cancel_reserved_allocations(
    *,
    order: Order,
) -> None:
    allocations = list(
        order.allocations
        .select_for_update()
        .filter(
            status=Allocation.Status.RESERVED,
        )
    )

    for allocation in allocations:
        allocation.cancel()


def _delete_reserved_allocations(
    *,
    order: Order,
) -> None:
    order.allocations.filter(
        status=Allocation.Status.RESERVED,
    ).delete()
