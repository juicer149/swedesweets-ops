"""
Order application services.

This module owns shared order lifecycle mutations and the existing draft
persistence workflow.

Persistence mechanics such as transaction boundaries and row locking are
centralized by orders.decorators.locked_order.

Channel-specific transition prerequisites are injected as policies.
Reservation persistence and accounting belong to reservations.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from customers.models import Customer
from orders.contracts import OrderTransitionPreparation
from orders.datatypes import (
    BuyerInput,
    OrderLineInput,
)
from orders.decorators import locked_order
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from products.models import Product
from products.units import (
    normalize_order_unit,
    quantity_to_units,
)
from reservations.selectors import (
    has_reservations_for_order,
)
from reservations.services import (
    MissingReservations,
    cancel_reservations_for_order,
    consume_reservations_for_order,
    delete_reservations_for_order,
)


@dataclass(frozen=True)
class NormalizedOrderLine:
    """Order line normalized to the operational fulfillment unit."""

    product: Product
    quantity: int


def _require_draft_for_edit(
    *,
    order: Order,
) -> None:
    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "Only draft orders can be edited; "
            f"current status is {order.status}"
        )


def _require_draft_for_discard(
    *,
    order: Order,
) -> None:
    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "Only draft orders can be discarded; "
            f"current status is {order.status}"
        )


def _require_draft_for_placement(
    *,
    order: Order,
) -> None:
    if order.status != Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "Only draft orders can be placed; "
            f"current status is {order.status}"
        )


def _require_placed_for_edit(
    *,
    order: Order,
) -> None:
    if order.status != Order.Status.PLACED:
        raise InvalidOrderOperation(
            "Only placed orders can be edited; "
            f"current status is {order.status}"
        )


def _require_placed_for_packing(
    *,
    order: Order,
) -> None:
    if order.status != Order.Status.PLACED:
        raise InvalidOrderOperation(
            f"Cannot pack order {order.pk}; "
            f"current status is {order.status}"
        )


def _require_cancellable(
    *,
    order: Order,
) -> None:
    if not order.can_be_cancelled:
        raise InvalidOrderOperation(
            f"Cannot cancel order {order.pk}; "
            f"current status is {order.status}"
        )


def buyer_from_customer(
    *,
    customer: Customer,
) -> BuyerInput:
    """Adapt a persisted customer to the buyer snapshot contract."""

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
    """Create a business-shaped order in DRAFT status."""

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
    """Return the customer's active business draft, creating one if needed."""

    draft = (
        Order.objects
        .select_for_update()
        .filter(
            channel=Order.Channel.BUSINESS,
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
        channel=Order.Channel.BUSINESS,
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
                channel=Order.Channel.BUSINESS,
                customer=customer,
                status=Order.Status.DRAFT,
            )
        )

    return order


@locked_order(
    guard=_require_draft_for_edit,
)
def replace_draft_order_lines(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace all lines on a draft order."""

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


@locked_order(
    guard=_require_draft_for_discard,
)
def discard_draft_order(
    *,
    order: Order,
) -> None:
    """Delete an unplaced draft order."""

    if has_reservations_for_order(order=order):
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
    preparation: OrderTransitionPreparation,
    user=None,
) -> Order:
    """Create a draft order and immediately place it.

    Creation remains business-shaped temporarily. The placement policy is
    supplied by the caller.
    """

    order = _create_draft_order(
        customer=customer,
        buyer=buyer_from_customer(
            customer=customer,
        ),
        lines=lines,
    )

    return place_order(order=order, preparation=preparation, user=user)


@locked_order(guard=_require_draft_for_placement)
def place_order(
    *,
    order: Order,
    preparation: OrderTransitionPreparation,
    user=None,
) -> Order:
    """Prepare a draft order and move it to PLACED."""

    preparation(order=order)
    order.mark_as_placed(user=user)
    return order


@locked_order(guard=_require_placed_for_edit)
def update_placed_order(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    preparation: OrderTransitionPreparation,
    user=None,
) -> Order:
    """Replace lines on a placed order and rebuild channel preparation."""

    normalized_lines = _normalize_order_lines(lines=lines)

    if not normalized_lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    delete_reservations_for_order(order=order)

    order.lines.all().delete()

    _create_order_lines(
        order=order,
        normalized_lines=normalized_lines,
    )
    preparation(order=order)
    order.mark_as_edited(user=user)

    return order


@locked_order(guard=_require_placed_for_packing)
def pack_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Consume existing reservations and move the order to PACKED.

    Reservation consumption remains shared for now. It can become an injected
    fulfillment preparation when multiple fulfillment strategies actually
    exist.
    """

    try:
        consume_reservations_for_order(
            order=order,
        )
    except MissingReservations as exc:
        raise InvalidOrderOperation(
            f"Order {order.pk} has no reserved allocations"
        ) from exc

    order.mark_as_packed(user=user)
    return order


@locked_order(guard=_require_cancellable)
def cancel_order(
    *,
    order: Order,
    user=None,
    reason: str = "",
    note: str = "",
) -> Order:
    """Cancel an order and release active reservations."""

    cancel_reservations_for_order(order=order)
    order.cancel(user=user, reason=reason, note=note)
    return order


@locked_order()
def deliver_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Move an order to DELIVERED.

    Order.mark_as_delivered owns the valid source-state rule.
    """

    order.mark_as_delivered(user=user)
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
        channel=Order.Channel.BUSINESS,
        customer=customer,
    )

    order.snapshot_buyer(buyer=buyer)
    order.save()

    _create_order_lines(order= order, normalized_lines= normalized_lines)
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
    line_inputs = list(lines)

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

    quantity_by_product_id: dict[int, int] = defaultdict(int)

    for line_input, product_id in resolved_inputs:
        try:
            product = products_by_id[product_id]
        except KeyError as exc:
            raise InvalidOrderOperation(
                f"Product {product_id} does not exist"
            ) from exc

        unit = normalize_order_unit(str(line_input.unit))

        quantity = quantity_to_units(
            product=product,
            quantity=line_input.quantity,
            unit=unit,
        )

        if quantity <= 0:
            raise InvalidOrderOperation(
                "order line quantity must be positive"
            )

        quantity_by_product_id[product_id] += quantity

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
