from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from business_portal.orders.list_viewmodels import (
    build_portal_order_page_rows,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from customers.models import CUSTOMER_COUNTRY_LABELS
from orders.models import Order
from orders.selectors import list_customer_orders


ACCOUNT_TAB_ACCOUNT = "account"
ACCOUNT_TAB_ORDERS = "orders"
ACCOUNT_TABS = {
    ACCOUNT_TAB_ACCOUNT,
    ACCOUNT_TAB_ORDERS,
}

ACCOUNT_ORDER_FILTER_OPTIONS = (
    (
        "",
        _("All"),
    ),
    (
        Order.Status.PLACED,
        Order.Status.PLACED.label,
    ),
    (
        Order.Status.PACKED,
        Order.Status.PACKED.label,
    ),
    (
        Order.Status.DELIVERED,
        Order.Status.DELIVERED.label,
    ),
    (
        Order.Status.CANCELLED,
        Order.Status.CANCELLED.label,
    ),
)


def _active_account_tab(
    value: str | None,
) -> str:
    if value in ACCOUNT_TABS:
        return value

    return ACCOUNT_TAB_ACCOUNT


def _build_account_orders_context(
    *,
    customer,
) -> dict:
    customer_orders = list(
        list_customer_orders(
            customer=customer,
        )
    )

    return {
        "order_rows": build_portal_order_page_rows(
            orders=customer_orders,
        ),
        "order_filter_options": ACCOUNT_ORDER_FILTER_OPTIONS,
    }


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
        _build_account_orders_context(
            customer=customer,
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
