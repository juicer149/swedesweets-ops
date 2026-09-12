from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from business_portal.orders.navbar_viewmodels import (
    build_business_navbar_cart,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from orders.selectors import (
    get_active_draft_order_for_customer,
)


@login_required
@require_GET
def navbar_cart_fragment(
    request,
):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    draft_order = (
        get_active_draft_order_for_customer(
            customer=customer,
        )
    )

    navbar_cart = (
        build_business_navbar_cart(
            draft_order=draft_order,
            language_code=request.LANGUAGE_CODE,
        )
    )

    return render(
        request,
        "includes/navbar_cart.html",
        {
            "navbar_cart": navbar_cart,
        },
    )
