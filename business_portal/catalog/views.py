from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from business.selectors import (
    list_business_catalog_entries,
)
from business_portal.catalog.viewmodels import (
    build_business_product_cards,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)


@login_required
def catalog(request):
    """Render the business customer's orderable catalog."""

    get_portal_customer_for_user(
        user=request.user,
    )

    entries = list_business_catalog_entries()

    product_cards = build_business_product_cards(
        entries=entries,
        language_code=request.LANGUAGE_CODE,
    )

    return render(
        request,
        "business_portal/catalog/index.html",
        {
            "product_cards": product_cards,
        },
    )
