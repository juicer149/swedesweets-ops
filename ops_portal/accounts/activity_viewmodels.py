from __future__ import annotations

from dataclasses import replace

from django.urls import reverse

from accounts.activity_viewmodels import (
    AccountActivityPresentation,
    build_account_activity_presentations,
)
from accounts.activity import AccountActivity
from customers.models import Customer
from inventory.models import InventoryBatch
from orders.models import Order
from products.models import Product


def build_ops_account_activity_presentations(
    activities: tuple[AccountActivity, ...],
) -> tuple[AccountActivityPresentation, ...]:
    presentations = build_account_activity_presentations(
        activities
    )

    return tuple(
        replace(
            presentation,
            target_href=_target_href(activity.target),
        )
        for activity, presentation in zip(
            activities,
            presentations,
            strict=True,
        )
    )


def _target_href(target: object) -> str:
    match target:
        case Order():
            return reverse(
                "orders:detail",
                kwargs={
                    "order_id": target.pk,
                },
            )

        case Product():
            return reverse(
                "ops_products:detail",
                kwargs={
                    "product_pk": target.pk,
                },
            )

        case InventoryBatch():
            return reverse(
                "inventory:detail",
                kwargs={
                    "batch_pk": target.pk,
                },
            )

        case Customer():
            return reverse(
                "ops_customers:detail",
                kwargs={
                    "customer_pk": target.pk,
                },
            )

    return ""
