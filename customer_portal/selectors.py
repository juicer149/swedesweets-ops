# customer_portal/selectors.py

from __future__ import annotations

from django.shortcuts import get_object_or_404

from accounts.models import CustomerMembership
from orders.models import Order
from orders.selectors import list_customer_orders


def get_portal_customer_for_user(*, user):
    membership = get_object_or_404(
        CustomerMembership.objects.select_related("customer"),
        user=user,
    )

    return membership.customer


def get_portal_order_for_user(
    *,
    user,
    order_id: int,
) -> Order:
    customer = get_portal_customer_for_user(user=user)

    return get_object_or_404(
        list_customer_orders(customer=customer),
        pk=order_id,
    )
