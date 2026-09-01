"""
Customer read selectors.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

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

class CustomerActivityKind(StrEnum):
    CREATED = "created"
    EDITED = "edited"
    ACTIVATED = "activated"
    DEACTIVATED = "deactivated"


@dataclass(frozen=True, slots=True)
class CustomerActivity:
    occurred_at: datetime
    kind: CustomerActivityKind
    customer: Customer


_CUSTOMER_ACTIVITY_SPECS = (
    (
        "created_by",
        "created_at",
        CustomerActivityKind.CREATED,
    ),
    (
        "edited_by",
        "edited_at",
        CustomerActivityKind.EDITED,
    ),
    (
        "activated_by",
        "activated_at",
        CustomerActivityKind.ACTIVATED,
    ),
    (
        "deactivated_by",
        "deactivated_at",
        CustomerActivityKind.DEACTIVATED,
    ),
)


def list_customer_activity_for_actor(
    *,
    actor,
    limit: int,
) -> tuple[CustomerActivity, ...]:
    activities: list[CustomerActivity] = []

    for actor_field, occurred_at_field, kind in _CUSTOMER_ACTIVITY_SPECS:
        customers = (
            Customer.objects
            .filter(
                **{
                    actor_field: actor,
                    f"{occurred_at_field}__isnull": False,
                }
            )
            .order_by(f"-{occurred_at_field}")[:limit]
        )

        activities.extend(
            CustomerActivity(
                occurred_at=getattr(
                    customer,
                    occurred_at_field,
                ),
                kind=kind,
                customer=customer,
            )
            for customer in customers
        )

    return tuple(
        sorted(
            activities,
            key=lambda activity: activity.occurred_at,
            reverse=True,
        )[:limit]
    )
