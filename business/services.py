from __future__ import annotations

from collections.abc import Iterable

from django.db import IntegrityError, transaction

from business.drafts import (
    build_business_order_draft,
    buyer_from_customer,
    resolve_business_order_lines,
)
from business.policies import (
    prepare_business_order_for_placement,
)
from customers.models import Customer
from orders.datatypes import OrderLineInput
from orders.models import Order
from orders.services import (
    create_draft_order as create_shared_draft_order,
    discard_draft_order as discard_shared_draft_order,
    place_order as place_shared_order,
    replace_draft_order_lines as replace_shared_draft_order_lines,
    update_placed_order as update_shared_placed_order,
)
from reservations.policies import (
    clear_order_reservations_before_line_replacement,
    require_order_without_reservations_before_discard,
)


@transaction.atomic
def create_draft_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
) -> Order:
    """Create a business order in DRAFT status."""

    draft = build_business_order_draft(
        customer=customer,
        lines=lines,
    )

    return create_shared_draft_order(
        draft=draft,
    )


@transaction.atomic
def create_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Create and immediately place an ordinary business order.

    The outer transaction makes draft persistence and placement one atomic
    business use-case.
    """

    order = create_draft_order(
        customer=customer,
        lines=lines,
    )

    return place_order(
        order=order,
        user=user,
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
        currency=Order.Currency.EUR,
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


def replace_draft_order_lines(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace the lines of a business draft order."""

    resolved_lines = resolve_business_order_lines(
        lines=lines,
    )

    return replace_shared_draft_order_lines(
        order=order,
        lines=resolved_lines,
        user=user,
    )


def discard_draft_order(
    *,
    order: Order,
) -> None:
    """Discard a business draft that owns no reservations."""

    discard_shared_draft_order(
        order=order,
        preparation=require_order_without_reservations_before_discard,
    )


def place_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Place an ordinary business draft order."""

    return place_shared_order(
        order=order,
        preparation=prepare_business_order_for_placement,
        user=user,
    )


def update_placed_order(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace lines and rebuild an ordinary business reservation."""

    resolved_lines = resolve_business_order_lines(
        lines=lines,
    )

    return update_shared_placed_order(
        order=order,
        lines=resolved_lines,
        before_replacement=(
            clear_order_reservations_before_line_replacement
        ),
        preparation=prepare_business_order_for_placement,
        user=user,
    )
