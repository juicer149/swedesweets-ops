"""
Shared order application services.

This module owns persistence and lifecycle mutations for already resolved
orders.

Sales channels resolve buyer input, products, quantities, prices and commercial
eligibility before calling this module.

Persistence mechanics such as transaction boundaries and row locking are
centralized by orders.decorators.locked_order.

Mutation-specific prerequisites are injected as policies.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from orders.contracts import OrderMutationPreparation
from orders.decorators import locked_order
from orders.drafts import (
    OrderDraft,
    ResolvedOrderLine,
)
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)


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


def _require_positive_quantity(
    *,
    quantity_in_units: int,
) -> None:
    if quantity_in_units <= 0:
        raise InvalidOrderOperation(
            "order line quantity must be positive"
        )


@transaction.atomic
def create_draft_order(
    *,
    draft: OrderDraft,
) -> Order:
    """Persist an already resolved order draft."""

    if not draft.lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    order = Order(
        channel=draft.channel,
        currency=draft.currency,
        customer=draft.customer,
        status=Order.Status.DRAFT,
    )

    order.snapshot_buyer(
        buyer=draft.buyer,
    )
    order.save()

    _create_order_lines(
        order=order,
        lines=draft.lines,
    )

    return order


@locked_order(
    guard=_require_draft_for_edit,
)
def add_draft_order_line(
    *,
    order: Order,
    line: ResolvedOrderLine,
    user=None,
) -> OrderLine:
    """Persist one already-resolved line on a mutable draft order.

    Sales-channel code resolves commercial eligibility before calling this
    function. Orders owns only durable OrderLine persistence.
    """

    _require_positive_quantity(
        quantity_in_units=line.quantity_in_units,
    )

    order_line = OrderLine.objects.create(
        order=order,
        product=line.product,
        quantity=line.quantity_in_units,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=line.quantity_in_units,
        unit_price_snapshot=line.unit_price_snapshot,
    )

    order.updated_at = timezone.now()
    order.save(
        update_fields=[
            "updated_at",
        ],
    )

    return order_line


@locked_order(
    guard=_require_draft_for_edit,
)
def replace_draft_order_lines(
    *,
    order: Order,
    lines: Iterable[ResolvedOrderLine],
    user=None,
) -> Order:
    """Replace lines using already resolved line data."""

    resolved_lines = tuple(
        lines
    )

    order.lines.all().delete()

    if resolved_lines:
        _create_order_lines(
            order=order,
            lines=resolved_lines,
        )

    order.updated_at = timezone.now()
    order.save(
        update_fields=[
            "updated_at",
        ],
    )

    return order


@locked_order(
    guard=_require_draft_for_edit,
)
def set_draft_order_line_quantity(
    *,
    order: Order,
    order_line_id: int,
    quantity_in_units: int,
    user=None,
) -> Order:
    """Set an already-resolved quantity on one draft order line."""

    _require_positive_quantity(
        quantity_in_units=quantity_in_units,
    )

    line = (
        order.lines
        .filter(
            pk=order_line_id,
        )
        .first()
    )

    if line is None:
        raise InvalidOrderOperation(
            "order line does not belong to this draft order"
        )

    line.quantity = quantity_in_units
    line.unit = OrderLine.Unit.STOCK_UNIT
    line.quantity_in_units = quantity_in_units
    line.save(
        update_fields=[
            "quantity",
            "unit",
            "quantity_in_units",
        ]
    )

    order.updated_at = timezone.now()
    order.save(
        update_fields=[
            "updated_at",
        ],
    )

    return order


@locked_order(
    guard=_require_draft_for_edit,
)
def remove_draft_order_line(
    *,
    order: Order,
    order_line_id: int,
    user=None,
) -> Order:
    """Remove one line from a draft order."""

    line = (
        order.lines
        .filter(
            pk=order_line_id,
        )
        .first()
    )

    if line is None:
        raise InvalidOrderOperation(
            "order line does not belong to this draft order"
        )

    line.delete()

    order.updated_at = timezone.now()
    order.save(
        update_fields=[
            "updated_at",
        ],
    )

    return order


@locked_order(
    guard=_require_draft_for_discard,
)
def discard_draft_order(
    *,
    order: Order,
    preparation: OrderMutationPreparation,
) -> None:
    """Prepare and delete an unplaced draft order."""

    preparation(
        order=order,
    )

    order.delete()


@locked_order(
    guard=_require_draft_for_placement,
)
def place_order(
    *,
    order: Order,
    preparation: OrderMutationPreparation,
    user=None,
) -> Order:
    """Prepare a draft order and move it to PLACED."""

    preparation(
        order=order,
    )

    order.mark_as_placed(
        user=user,
    )

    return order


@locked_order(
    guard=_require_placed_for_edit,
)
def update_placed_order(
    *,
    order: Order,
    lines: Iterable[ResolvedOrderLine],
    before_replacement: OrderMutationPreparation,
    preparation: OrderMutationPreparation,
    user=None,
) -> Order:
    """Replace resolved lines and rebuild mutation prerequisites."""

    resolved_lines = tuple(
        lines
    )

    if not resolved_lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    before_replacement(
        order=order,
    )

    order.lines.all().delete()

    _create_order_lines(
        order=order,
        lines=resolved_lines,
    )

    preparation(
        order=order,
    )

    order.mark_as_edited(
        user=user,
    )

    return order


@locked_order(
    guard=_require_placed_for_packing,
)
def pack_order(
    *,
    order: Order,
    preparation: OrderMutationPreparation,
    user=None,
) -> Order:
    """Prepare a placed order and move it to PACKED."""

    preparation(
        order=order,
    )

    order.mark_as_packed(
        user=user,
    )

    return order


@locked_order(
    guard=_require_cancellable,
)
def cancel_order(
    *,
    order: Order,
    preparation: OrderMutationPreparation,
    user=None,
    reason: str = "",
    note: str = "",
) -> Order:
    """Prepare an order and move it to CANCELLED."""

    preparation(
        order=order,
    )

    order.cancel(
        user=user,
        reason=reason,
        note=note,
    )

    return order


@locked_order()
def deliver_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Move an order to DELIVERED."""

    order.mark_as_delivered(
        user=user,
    )

    return order


def _create_order_lines(
    *,
    order: Order,
    lines: Iterable[ResolvedOrderLine],
) -> None:
    OrderLine.objects.bulk_create(
        [
            OrderLine(
                order=order,
                product=line.product,
                quantity=line.quantity_in_units,
                unit=OrderLine.Unit.STOCK_UNIT,
                quantity_in_units=line.quantity_in_units,
                unit_price_snapshot=line.unit_price_snapshot,
            )
            for line in lines
        ]
    )
