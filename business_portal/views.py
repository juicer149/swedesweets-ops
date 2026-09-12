from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from business_portal.selectors import (
    get_portal_customer_for_user,
)
from business_portal.viewmodels import (
    RECENT_PORTAL_ORDER_LIMIT,
    build_portal_home_context,
)
from orders.selectors import (
    get_active_draft_order_for_customer,
    list_customer_orders,
)


@login_required
def index(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    active_draft_order = (
        get_active_draft_order_for_customer(
            customer=customer,
        )
    )

    recent_orders = tuple(
        list_customer_orders(
            customer=customer,
        )[:RECENT_PORTAL_ORDER_LIMIT]
    )

    context = build_portal_home_context(
        customer=customer,
        recent_orders=recent_orders,
        active_draft_order=active_draft_order,
    ).as_dict()

    return render(
        request,
        "business_portal/index.html",
        context,
    )


@login_required
def contact(request):
    return render(
        request,
        "business_portal/contact.html",
    )
