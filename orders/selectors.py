"""
Order read selectors.

This module owns read-side order queries used by order pages, customer detail
pages, dashboard summaries, and packing workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from django.db.models import (
    Case,
    Count,
    IntegerField,
    Max,
    QuerySet,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from common.table_tools import normalize_sort
from customers.models import Customer
from orders.datatypes import PickLine
from orders.models import Order
from reservations.datatypes import ReservationPick
from reservations.selectors import (
    list_consumed_picks_for_order,
    list_reserved_picks_for_order,
)

ORDER_HISTORY_STATUSES = (
    Order.Status.PLACED,
    Order.Status.PACKED,
    Order.Status.DELIVERED,
    Order.Status.CANCELLED,
)

DEFAULT_ORDER_SORT = "status"

ORDER_SORTS: dict[str, tuple[str, ...]] = {
    "order": ("id",),
    "-order": ("-id",),
    "customer": (
        "customer__name",
        "id",
    ),
    "-customer": (
        "-customer__name",
        "id",
    ),
    "created": (
        "created_at",
        "id",
    ),
    "-created": (
        "-created_at",
        "-id",
    ),
    "status": (
        "status_rank",
        "-id",
    ),
    "-status": (
        "-status_rank",
        "-id",
    ),
    "quantity": (
        "total_quantity",
        "id",
    ),
    "-quantity": (
        "-total_quantity",
        "id",
    ),
}

CUSTOMER_ORDER_SORTS: dict[str, tuple[str, ...]] = {
    "order": ("id",),
    "-order": ("-id",),
    "created": (
        "created_at",
        "id",
    ),
    "-created": (
        "-created_at",
        "-id",
    ),
    "status": (
        "status_rank",
        "-id",
    ),
    "-status": (
        "-status_rank",
        "-id",
    ),
    "quantity": (
        "total_quantity",
        "id",
    ),
    "-quantity": (
        "-total_quantity",
        "id",
    ),
}

DEFAULT_CUSTOMER_ORDER_SORT = DEFAULT_ORDER_SORT


@dataclass(frozen=True, slots=True)
class CustomerOrderSummary:
    total_orders: int
    placed_orders: int
    packed_orders: int
    delivered_orders: int
    cancelled_orders: int
    last_ordered_at: Any | None


def list_orders(
    *,
    status: str | None = None,
    sort: str | None = None,
) -> QuerySet[Order]:
    """Return orders for the operational order list.

    Invalid querystring values fall back to the default ordering.

    Drafts are work-in-progress and are excluded from default history.
    """

    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=ORDER_SORTS,
        default_sort=DEFAULT_ORDER_SORT,
    )

    orders = (
        Order.objects
        .select_related("customer")
        .annotate(
            **_order_summary_annotations(),
            status_rank=_status_rank_expression(),
        )
    )

    orders = _apply_order_history_status_filter(
        orders,
        status=status,
    )

    return orders.order_by(
        *ORDER_SORTS[normalized_sort]
    )


def list_customer_orders(
    *,
    customer,
    status: str | None = None,
    sort: str | None = None,
) -> QuerySet[Order]:
    """Return order history scoped to one customer."""

    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=CUSTOMER_ORDER_SORTS,
        default_sort=DEFAULT_CUSTOMER_ORDER_SORT,
    )

    orders = (
        Order.objects
        .select_related("customer")
        .filter(
            customer=customer,
        )
        .annotate(
            **_order_summary_annotations(),
            status_rank=_status_rank_expression(),
        )
    )

    orders = _apply_order_history_status_filter(
        orders,
        status=status,
    )

    return orders.order_by(
        *CUSTOMER_ORDER_SORTS[normalized_sort]
    )


def get_customer_order_summary(
    *,
    customer: Customer,
) -> CustomerOrderSummary:
    """Return order counts and latest order timestamp for a customer."""

    orders = _order_history_queryset().filter(
        customer=customer,
    )

    stats = orders.aggregate(
        total_orders=Count("id"),
        last_ordered_at=Max("created_at"),
    )

    orders_by_status = {
        row["status"]: row["count"]
        for row in (
            orders
            .values("status")
            .annotate(
                count=Count("id"),
            )
        )
    }

    return CustomerOrderSummary(
        total_orders=stats["total_orders"] or 0,
        placed_orders=orders_by_status.get(
            Order.Status.PLACED,
            0,
        ),
        packed_orders=orders_by_status.get(
            Order.Status.PACKED,
            0,
        ),
        delivered_orders=orders_by_status.get(
            Order.Status.DELIVERED,
            0,
        ),
        cancelled_orders=orders_by_status.get(
            Order.Status.CANCELLED,
            0,
        ),
        last_ordered_at=stats["last_ordered_at"],
    )


def get_active_draft_order_for_customer(
    *,
    customer,
) -> Order | None:
    """Return the customer's active business draft, if one exists."""

    return (
        Order.objects
        .filter(
            channel=Order.Channel.BUSINESS,
            customer=customer,
            status=Order.Status.DRAFT,
        )
        .prefetch_related("lines")
        .order_by(
            "created_at",
            "id",
        )
        .first()
    )


def list_placed_orders_for_dashboard(
    *,
    limit: int = 3,
) -> QuerySet[Order]:
    """Return oldest placed orders for operational handling."""

    return _list_orders_for_dashboard(
        status=Order.Status.PLACED,
        limit=limit,
    )


def list_packed_orders_for_dashboard(
    *,
    limit: int = 3,
) -> QuerySet[Order]:
    """Return oldest packed orders for operational handling."""

    return _list_orders_for_dashboard(
        status=Order.Status.PACKED,
        limit=limit,
    )


def count_placed_orders() -> int:
    return Order.objects.filter(
        status=Order.Status.PLACED,
    ).count()


def count_packed_orders() -> int:
    return Order.objects.filter(
        status=Order.Status.PACKED,
    ).count()


def get_packaging_list(
    *,
    order: Order,
) -> list[PickLine]:
    picks = list_reserved_picks_for_order(
        order=order,
    )

    return [
        _build_pick_line(
            pick=pick,
        )
        for pick in picks
    ]


def get_packed_lines(
    *,
    order: Order,
) -> list[PickLine]:
    picks = list_consumed_picks_for_order(
        order=order,
    )

    return [
        _build_pick_line(
            pick=pick,
        )
        for pick in picks
    ]


class OrderActivityKind(StrEnum):
    PLACED = "placed"
    PACKED = "packed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    EDITED = "edited"


@dataclass(frozen=True, slots=True)
class OrderActivity:
    occurred_at: datetime
    kind: OrderActivityKind
    order: Order


_ORDER_ACTIVITY_SPECS = (
    (
        "placed_by",
        "placed_at",
        OrderActivityKind.PLACED,
    ),
    (
        "packed_by",
        "packed_at",
        OrderActivityKind.PACKED,
    ),
    (
        "delivered_by",
        "delivered_at",
        OrderActivityKind.DELIVERED,
    ),
    (
        "cancelled_by",
        "cancelled_at",
        OrderActivityKind.CANCELLED,
    ),
    (
        "edited_by",
        "edited_at",
        OrderActivityKind.EDITED,
    ),
)


def list_order_activity_for_actor(
    *,
    actor,
    limit: int,
) -> tuple[OrderActivity, ...]:
    activities: list[OrderActivity] = []

    for actor_field, occurred_at_field, kind in _ORDER_ACTIVITY_SPECS:
        orders = (
            Order.objects
            .filter(
                **{
                    actor_field: actor,
                    f"{occurred_at_field}__isnull": False,
                }
            )
            .select_related("customer")
            .order_by(f"-{occurred_at_field}")[:limit]
        )

        activities.extend(
            OrderActivity(
                occurred_at=getattr(
                    order,
                    occurred_at_field,
                ),
                kind=kind,
                order=order,
            )
            for order in orders
        )

    return tuple(
        sorted(
            activities,
            key=lambda activity: activity.occurred_at,
            reverse=True,
        )[:limit]
    )


def _build_pick_line(
    *,
    pick: ReservationPick,
) -> PickLine:
    return PickLine(
        sku=pick.sku,
        product_name=pick.product_name,
        batch_id=pick.batch_code,
        location=pick.location,
        quantity=pick.quantity,
        quantity_label=pick.quantity_label,
    )


def _order_history_queryset() -> QuerySet[Order]:
    """Return completed or operational order history, excluding drafts."""

    return Order.objects.exclude(
        status=Order.Status.DRAFT,
    )


def _apply_order_history_status_filter(
    orders: QuerySet[Order],
    *,
    status: str | None,
) -> QuerySet[Order]:
    """Apply optional status filtering to order history."""

    if status in Order.Status.values:
        return orders.filter(
            status=status,
        )

    return orders.exclude(
        status=Order.Status.DRAFT,
    )


def _order_summary_annotations() -> dict[str, object]:
    return {
        "product_count": Coalesce(
            Count(
                "lines",
                distinct=True,
            ),
            Value(0),
            output_field=IntegerField(),
        ),
        "total_quantity": Coalesce(
            Sum("lines__quantity_in_units"),
            Value(0),
            output_field=IntegerField(),
        ),
    }


def _status_rank_expression() -> Case:
    return Case(
        When(
            status=Order.Status.PLACED,
            then=Value(1),
        ),
        When(
            status=Order.Status.PACKED,
            then=Value(2),
        ),
        When(
            status=Order.Status.DELIVERED,
            then=Value(3),
        ),
        When(
            status=Order.Status.CANCELLED,
            then=Value(4),
        ),
        When(
            status=Order.Status.DRAFT,
            then=Value(5),
        ),
        default=Value(99),
        output_field=IntegerField(),
    )


def _list_orders_for_dashboard(
    *,
    status: str,
    limit: int,
) -> QuerySet[Order]:
    return (
        Order.objects
        .filter(
            status=status,
        )
        .select_related("customer")
        .annotate(
            **_order_summary_annotations()
        )
        .order_by(
            "created_at",
            "id",
        )[:limit]
    )
