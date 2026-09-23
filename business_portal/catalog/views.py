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
from common.catalog.contracts import CatalogOfferKind
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
    """Parse an optional catalog selection from form input.

    Empty input requests the current standard BUSINESS offer.

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


def _resolve_catalog_offer_id(
    *,
    product: Product,
    commercial_price_id: int | None,
) -> int:
    """Resolve transport-level selection to a persistent offer identity.

    A missing id is a portal shorthand for the product's current standard
    BUSINESS offer. The business service itself only accepts persistent
    CommercialPrice identities.
    """

    if commercial_price_id is not None:
        return commercial_price_id

    catalog_product = get_business_catalog_product(
        product_id=product.id,
    )

    if catalog_product is None:
        raise InvalidOrderOperation(
            "product is not available in the business catalog"
        )

    for offer in catalog_product.offers:
        if offer.kind == CatalogOfferKind.STANDARD:
            return offer.commercial_price_id

    raise InvalidOrderOperation(
        "standard business offer is not currently available"
    )


def _parse_quantity(
    raw_value: str | None,
) -> int:
    """Parse catalog quantity from form input.

    Missing input preserves the legacy catalog behavior and means one unit.

    An explicitly submitted quantity must contain a positive integer.
    Empty, non-integer and non-positive values are rejected.
    """

    if raw_value is None:
        return 1

    value = raw_value.strip()

    if not value:
        raise InvalidOrderOperation(
            "quantity is required"
        )

    try:
        quantity = int(value)
    except ValueError as exc:
        raise InvalidOrderOperation(
            "invalid quantity"
        ) from exc

    if quantity <= 0:
        raise InvalidOrderOperation(
            "quantity must be greater than zero"
        )

    return quantity


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
        requested_commercial_price_id = (
            _parse_commercial_price_id(
                request.POST.get(
                    "commercial_price_id"
                )
            )
        )

        quantity = _parse_quantity(
            request.POST.get(
                "quantity"
            )
        )

        commercial_price_id = _resolve_catalog_offer_id(
            product=product,
            commercial_price_id=(
                requested_commercial_price_id
            ),
        )

        add_catalog_offer_to_draft_order(
            customer=customer,
            product=product,
            commercial_price_id=commercial_price_id,
            quantity=quantity,
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
