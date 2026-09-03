from __future__ import annotations

from django.shortcuts import get_object_or_404

from accounts.models import CustomerMembership


def get_portal_customer_for_user(*, user):
    membership = get_object_or_404(
        CustomerMembership.objects.select_related("customer"),
        user=user,
    )

    return membership.customer
