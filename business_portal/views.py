from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from business_portal.orders.views import (
    build_portal_orders_context,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from customers.models import CUSTOMER_COUNTRY_LABELS


ACCOUNT_TAB_ACCOUNT = "account"
ACCOUNT_TAB_ORDERS = "orders"
ACCOUNT_TABS = {
    ACCOUNT_TAB_ACCOUNT,
    ACCOUNT_TAB_ORDERS,
}


def _active_account_tab(
    value: str | None,
) -> str:
    if value in ACCOUNT_TABS:
        return value

    return ACCOUNT_TAB_ACCOUNT


@login_required
@require_GET
def index(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    active_tab = _active_account_tab(
        request.GET.get(
            "tab"
        )
    )

    context = {
        "customer": customer,
        "country_label": CUSTOMER_COUNTRY_LABELS.get(
            customer.country,
            customer.country,
        ),
        "active_tab": active_tab,
    }

    context.update(
        build_portal_orders_context(
            request=request,
            customer=customer,
            base_path=reverse(
                "business_portal:index"
            ),
        )
    )

    return render(
        request,
        "business_portal/index.html",
        context,
    )


@login_required
@require_GET
def contact(request):
    return render(
        request,
        "storefront/contact.html",
    )


@login_required
@require_GET
def faq(request):
    return render(
        request,
        "storefront/faq.html",
        {
            "contact_url": reverse(
                "business_portal:contact"
            ),
        },
    )
