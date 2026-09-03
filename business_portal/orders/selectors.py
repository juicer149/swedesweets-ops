from __future__ import annotations

from django.shortcuts import get_object_or_404

from business_portal.selectors import get_portal_customer_for_user
from orders.models import Order
from orders.selectors import list_customer_orders


def get_portal_order_for_user(
    *,
    user,
    order_id: int,
) -> Order:
    customer = get_portal_customer_for_user(
        user=user,
    )

    return get_object_or_404(
        list_customer_orders(
            customer=customer,
        ),
        pk=order_id,
    )
