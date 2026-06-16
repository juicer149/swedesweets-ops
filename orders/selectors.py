"""
Order read selectors.

This module owns read-side order queries used by order pages, customer detail
pages, dashboard summaries, and packing workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from orders.models import Allocation, Order


DEFAULT_ORDER_SORT = "status"

ORDER_SORTS: dict[str, tuple[str, ...]] = {
    "order": ("id",),
    "-order": ("-id",),
    "customer": ("customer__name", "id"),
    "-customer": ("-customer__name", "id"),
    "created": ("created_at", "id"),
    "-created": ("-created_at", "-id"),
    "status": ("status_rank", "-id"),
    "-status": ("-status_rank", "-id"),
    "quantity": ("total_quantity", "id"),
    "-quantity": ("-total_quantity", "id"),
}


CUSTOMER_ORDER_SORTS: dict[str, tuple[str, ...]] = {
    "order": ("id",),
    "-order": ("-id",),
    "created": ("created_at", "id"),
    "-created": ("-created_at", "-id"),
    "status": ("status_rank", "-id"),
    "-status": ("-status_rank", "-id"),
    "quantity": ("total_quantity", "id"),
    "-quantity": ("-total_quantity", "id"),
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
    """Return orders for the orders list page.

    Invalid querystring values are ignored deliberately, so bad user input falls
    back to the default operational ordering instead of crashing the page.

    Default ordering uses a domain-specific status rank:

        placed -> packed -> delivered -> cancelled -> draft
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

    if status in Order.Status.values:
        orders = orders.filter(status=status)

    return orders.order_by(*ORDER_SORTS[normalized_sort])


def list_customer_orders(
    *,
    customer,
    status: str | None = None,
    sort: str | None = None,
) -> QuerySet[Order]:
    """Return orders scoped to one customer.

    This is used by customer-facing views and customer detail pages.

    The database query owns filtering and sorting. The caller must provide the
    already-authorized customer object; customer portal views should get that
    customer from the authenticated user's customer membership.
    """

    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=CUSTOMER_ORDER_SORTS,
        default_sort=DEFAULT_CUSTOMER_ORDER_SORT,
    )

    orders = (
        Order.objects
        .select_related("customer")
        .filter(customer=customer)
        .annotate(
            **_order_summary_annotations(),
            status_rank=_status_rank_expression(),
        )
    )

    if status in Order.Status.values:
        orders = orders.filter(status=status)

    return orders.order_by(*CUSTOMER_ORDER_SORTS[normalized_sort])


def get_customer_order_summary(*, customer: Customer) -> CustomerOrderSummary:
    """Return order counts and latest order timestamp for a customer."""

    stats = (
        Order.objects
        .filter(customer=customer)
        .aggregate(
            total_orders=Count("id"),
            last_ordered_at=Max("created_at"),
        )
    )

    orders_by_status = {
        row["status"]: row["count"]
        for row in (
            Order.objects
            .filter(customer=customer)
            .values("status")
            .annotate(count=Count("id"))
        )
    }

    return CustomerOrderSummary(
        total_orders=stats["total_orders"] or 0,
        placed_orders=orders_by_status.get(Order.Status.PLACED, 0),
        packed_orders=orders_by_status.get(Order.Status.PACKED, 0),
        delivered_orders=orders_by_status.get(Order.Status.DELIVERED, 0),
        cancelled_orders=orders_by_status.get(Order.Status.CANCELLED, 0),
        last_ordered_at=stats["last_ordered_at"],
    )


def get_active_draft_order_for_customer(
    *,
    customer,
) -> Order | None:
    return (
        Order.objects
        .filter(
            customer=customer,
            status=Order.Status.DRAFT,
        )
        .prefetch_related("lines")
        .order_by("created_at", "id")
        .first()
    )


def list_placed_orders_for_dashboard(
    *,
    limit: int = 3,
) -> QuerySet[Order]:
    """Return placed orders for the dashboard overview.

    Oldest first because these orders have waited longest to be packed.
    """

    return _list_orders_for_dashboard(
        status=Order.Status.PLACED,
        limit=limit,
    )


def list_packed_orders_for_dashboard(
    *,
    limit: int = 3,
) -> QuerySet[Order]:
    """Return packed orders for the dashboard overview.

    Oldest first because these orders have waited longest to be delivered.
    """

    return _list_orders_for_dashboard(
        status=Order.Status.PACKED,
        limit=limit,
    )


def count_placed_orders() -> int:
    return Order.objects.filter(status=Order.Status.PLACED).count()


def count_packed_orders() -> int:
    return Order.objects.filter(status=Order.Status.PACKED).count()


def get_packaging_list(*, order: Order) -> list[PickLine]:
    allocations = (
        order.allocations
        .filter(status=Allocation.Status.RESERVED)
        .select_related("batch", "batch__product")
        .order_by("order_line_id", "batch__best_before", "batch__batch_id")
    )

    return [
        _build_pick_line(allocation)
        for allocation in allocations
    ]


def get_packed_lines(*, order: Order) -> list[PickLine]:
    allocations = (
        order.allocations
        .filter(status=Allocation.Status.CONSUMED)
        .select_related("batch", "batch__product")
        .order_by("order_line_id", "batch__best_before", "batch__batch_id")
    )

    return [
        _build_pick_line(allocation)
        for allocation in allocations
    ]


def _build_pick_line(allocation: Allocation) -> PickLine:
    product = allocation.batch.product

    return PickLine(
        sku=product.sku,
        product_name=product.catalog_label,
        batch_id=allocation.batch.batch_id,
        location=allocation.batch.location,
        quantity=allocation.quantity,
        quantity_label=product.stock_quantity_label(allocation.quantity),
    )


def _order_summary_annotations() -> dict[str, object]:
    return {
        "product_count": Coalesce(
            Count("lines", distinct=True),
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
        When(status=Order.Status.PLACED, then=Value(1)),
        When(status=Order.Status.PACKED, then=Value(2)),
        When(status=Order.Status.DELIVERED, then=Value(3)),
        When(status=Order.Status.CANCELLED, then=Value(4)),
        When(status=Order.Status.DRAFT, then=Value(5)),
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
        .filter(status=status)
        .select_related("customer")
        .annotate(**_order_summary_annotations())
        .order_by("created_at", "id")[:limit]
    )
