from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from customer_portal.selectors import get_portal_customer_for_user
from customer_portal.viewmodels import (
    RECENT_PORTAL_ORDER_LIMIT,
    build_portal_home_context,
)
from orders.selectors import (
    get_customer_order_summary,
    list_customer_orders,
)


@login_required
def index(request):
    customer = get_portal_customer_for_user(user=request.user)

    context = build_portal_home_context(
        customer=customer,
        order_summary=get_customer_order_summary(customer=customer),
        recent_orders=tuple(
            list_customer_orders(customer=customer)[:RECENT_PORTAL_ORDER_LIMIT]
        ),
    ).as_dict()

    return render(request, "customer_portal/index.html", context)


@login_required
def orders(request):
    return HttpResponse("My orders")


@login_required
def place_order(request):
    return HttpResponse("Place order")


@login_required
def order_detail(request, order_id: int):
    return HttpResponse(f"My order {order_id}")


@login_required
def catalog(request):
    return HttpResponse("Customer catalog")


@login_required
def profile(request):
    return HttpResponse("My profile")


@login_required
def edit_profile(request):
    return HttpResponse("Edit my profile")


@login_required
def contact(request):
    return HttpResponse("Contact SwedeSweets")
