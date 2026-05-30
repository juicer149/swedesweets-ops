"""
Customer read selectors.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Max, QuerySet

from common.table_tools import normalize_sort
from customers.models import Customer
from orders.models import Order


DEFAULT_CUSTOMER_SORT = "customer"

CUSTOMER_SORTS: dict[str, tuple[str, ...]] = {
    "customer": ("name", "email"),
    "-customer": ("-name", "email"),
    "email": ("email", "name"),
    "-email": ("-email", "name"),
    "phone": ("phone_number", "name"),
    "-phone": ("-phone_number", "name"),
    "city": ("city", "name", "email"),
    "-city": ("-city", "name", "email"),
    "country": ("country", "city", "name"),
    "-country": ("-country", "city", "name"),
}


@dataclass(frozen=True)
class CustomerOrderSummary:
    total_orders: int
    placed_orders: int
    packed_orders: int
    delivered_orders: int
    cancelled_orders: int
    last_ordered_at: object | None


def list_customers(
    *,
    sort: str | None = None,
) -> QuerySet[Customer]:
    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=CUSTOMER_SORTS,
        default_sort=DEFAULT_CUSTOMER_SORT,
    )

    return Customer.objects.order_by(*CUSTOMER_SORTS[normalized_sort])


def get_customer_order_summary(*, customer: Customer) -> CustomerOrderSummary:
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
