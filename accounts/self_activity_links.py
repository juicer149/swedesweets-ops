from __future__ import annotations

from django.urls import reverse

from accounts.roles import Capability, RoleSpec
from accounts.activity import AccountActivity
from customers.models import Customer
from inventory.models import InventoryBatch
from orders.models import Order
from products.models import Product


def self_activity_target_href(
    *,
    activity: AccountActivity,
    role_spec: RoleSpec,
) -> str:
    target = activity.target

    if role_spec.allows(Capability.VIEW_OWN_ORDERS):
        return _business_customer_target_href(target)

    if role_spec.allows(Capability.VIEW_ORDERS):
        return _staff_target_href(target)

    return ""


def _business_customer_target_href(target: object) -> str:
    if not isinstance(target, Order):
        return ""

    return reverse(
        "business_portal:order_detail",
        kwargs={"order_id": target.pk},
    )


def _staff_target_href(target: object) -> str:
    match target:
        case Order():
            return reverse(
                "orders:detail",
                kwargs={"order_id": target.pk},
            )

        case Product():
            return reverse(
                "products:detail",
                kwargs={"product_pk": target.pk},
            )

        case InventoryBatch():
            return reverse(
                "inventory:detail",
                kwargs={"batch_pk": target.pk},
            )

        case Customer():
            return reverse(
                "customers:detail",
                kwargs={"customer_pk": target.pk},
            )

    return ""
