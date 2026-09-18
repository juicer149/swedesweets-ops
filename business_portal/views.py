from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from business_portal.selectors import (
    get_portal_customer_for_user,
)
from customers.models import CUSTOMER_COUNTRY_LABELS


@login_required
@require_GET
def index(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    return render(
        request,
        "business_portal/index.html",
        {
            "customer": customer,
            "country_label": CUSTOMER_COUNTRY_LABELS.get(
                customer.country,
                customer.country,
            ),
        },
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
