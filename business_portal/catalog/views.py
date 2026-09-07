from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from business.selectors import (
    list_business_catalog_entries,
)
from business.services import add_product_to_draft_order
from business_portal.catalog.viewmodels import (
    build_business_product_cards,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from orders.errors import InvalidOrderOperation
from products.models import Product


@login_required
@require_POST
def add_product(request, product_id: int):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    product = get_object_or_404(
        Product,
        pk=product_id,
    )

    try:
        add_product_to_draft_order(
            customer=customer,
            product=product,
            quantity=1,
            user=request.user,
        )
    except InvalidOrderOperation as error:
        messages.error(
            request,
            str(error),
        )
    else:
        messages.success(
            request,
            _("%(product)s added to your order.")
            % {
                "product": product.display_name,
            },
        )

    return redirect(
        "business_portal:catalog"
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
