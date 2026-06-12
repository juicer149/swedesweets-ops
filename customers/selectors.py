"""
Customer read selectors.
"""

from __future__ import annotations

from django.db.models import QuerySet

from common.table_tools import normalize_sort
from customers.models import Customer


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
