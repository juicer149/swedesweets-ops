from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from business_portal.selectors import (
    get_portal_customer_for_user,
)
from business_portal.viewmodels import (
    RECENT_PORTAL_ORDER_LIMIT,
    build_portal_home_context,
)
from orders.selectors import (
    get_active_draft_order_for_customer,
    get_customer_order_summary,
    list_customer_orders,
)


@login_required
def index(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    active_draft_order = get_active_draft_order_for_customer(
        customer=customer,
    )

    context = build_portal_home_context(
        customer=customer,
        order_summary=get_customer_order_summary(
            customer=customer,
        ),
        recent_orders=tuple(
            list_customer_orders(
                customer=customer,
            )[:RECENT_PORTAL_ORDER_LIMIT]
        ),
        active_draft_order=active_draft_order,
    ).as_dict()

    return render(
        request,
        "business_portal/index.html",
        context,
    )


@login_required
def catalog(request):
    return HttpResponse(
        _("Customer catalog")
    )


@login_required
def contact(request):
    return render(
        request,
        "business_portal/contact.html",
    )
