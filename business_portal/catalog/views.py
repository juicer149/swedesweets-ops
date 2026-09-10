from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
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
    get_business_catalog_product,
    list_business_catalog_products,
)
from business.services import (
    add_catalog_offer_to_draft_order,
)
from business_portal.catalog.detail_viewmodels import (
    build_business_catalog_product_detail_context,
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


def _parse_commercial_price_id(
    raw_value: str | None,
) -> int | None:
    """Parse one catalog selection from form input.

    Empty means the explicit unpriced standard Business offer.

    Any non-empty value must be a positive integer CommercialPrice id.
    """

    if raw_value is None:
        return None

    value = raw_value.strip()

    if not value:
        return None

    try:
        commercial_price_id = int(value)
    except ValueError as exc:
        raise InvalidOrderOperation(
            "invalid business offer"
        ) from exc

    if commercial_price_id <= 0:
        raise InvalidOrderOperation(
            "invalid business offer"
        )

    return commercial_price_id


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
        commercial_price_id = (
            _parse_commercial_price_id(
                request.POST.get(
                    "commercial_price_id"
                )
            )
        )

        add_catalog_offer_to_draft_order(
            customer=customer,
            product=product,
            commercial_price_id=commercial_price_id,
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
    """Render one currently orderable Business catalog product."""

    get_portal_customer_for_user(
        user=request.user,
    )

    catalog_product = get_business_catalog_product(
        product_id=product_id,
    )

    if catalog_product is None:
        raise Http404(
            "Product is not available in the business catalog."
        )

    context = (
        build_business_catalog_product_detail_context(
            catalog_product=catalog_product,
            language_code=request.LANGUAGE_CODE,
        )
    )

    return render(
        request,
        "business_portal/catalog/detail.html",
        context.as_dict(),
    )
