from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from business.selectors import (
    get_business_catalog_entry,
    list_business_catalog_products,
)
from business.services import (
    add_product_to_draft_order,
)
from business_portal.catalog.viewmodels import (
    build_business_catalog_payload,
    build_business_product_cards,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from orders.errors import InvalidOrderOperation
from products.models import Product


def _wants_json(request) -> bool:
    return (
        "application/json"
        in request.headers.get(
            "Accept",
            "",
        )
    )


@login_required
@require_POST
def add_product(
    request,
    product_id: int,
):
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
        message = str(error)

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": False,
                    "message": message,
                },
                status=400,
            )

        messages.error(
            request,
            message,
        )

    else:
        message = _(
            "%(product)s added to your order."
        ) % {
            "product": product.display_name,
        }

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": True,
                    "message": message,
                }
            )

        messages.success(
            request,
            message,
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

    catalog_products = (
        list_business_catalog_products()
    )

    product_cards = build_business_product_cards(
        products=catalog_products,
        language_code=request.LANGUAGE_CODE,
    )

    catalog_data = build_business_catalog_payload(
        product_cards=product_cards,
    )

    return render(
        request,
        "business_portal/catalog/index.html",
        {
            "product_cards": product_cards,
            "catalog_data": catalog_data,
        },
    )


@login_required
def product_detail(
    request,
    product_id: int,
):
    """Temporary business catalog product detail endpoint."""

    get_portal_customer_for_user(
        user=request.user,
    )

    entry = get_business_catalog_entry(
        product_id=product_id,
    )

    if entry is None:
        raise Http404(
            "Product is not available in the business catalog."
        )

    return HttpResponse(
        entry.product.display_name
    )
