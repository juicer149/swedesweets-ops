from __future__ import annotations

from django.contrib import messages
from django.http import (
    Http404,
    HttpRequest,
    JsonResponse,
)
from django.shortcuts import (
    redirect,
    render,
)
from django.utils.translation import gettext as _
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from retail.services import (
    InvalidRetailCart,
    remove_retail_cart_line,
    update_retail_cart_line_quantity,
)
from storefront.cart import (
    mark_retail_cart_active,
)
from storefront.cart_selectors import (
    get_retail_cart,
    get_retail_cart_line,
)
from storefront.navbar_viewmodels import (
    build_retail_navbar_cart,
)


def _wants_json(
    request: HttpRequest,
) -> bool:
    return (
        "application/json"
        in request.headers.get(
            "Accept",
            "",
        )
    )


def _get_request_cart(
    request: HttpRequest,
):
    return get_retail_cart(
        cart_id=getattr(
            request,
            "retail_cart_id",
            None,
        ),
    )


def _get_request_cart_or_404(
    request: HttpRequest,
):
    cart = _get_request_cart(
        request
    )

    if cart is None:
        raise Http404(
            "Retail cart does not exist."
        )

    return cart


def _get_request_cart_line_or_404(
    *,
    cart,
    cart_line_id: int,
):
    line = get_retail_cart_line(
        cart=cart,
        line_id=cart_line_id,
    )

    if line is None:
        raise Http404(
            "Retail cart line does not exist."
        )

    return line


def _parse_quantity(
    raw_value: str | None,
) -> int:
    if raw_value is None:
        raise InvalidRetailCart(
            "quantity is required"
        )

    value = raw_value.strip()

    if not value:
        raise InvalidRetailCart(
            "quantity is required"
        )

    try:
        quantity = int(value)
    except ValueError as exc:
        raise InvalidRetailCart(
            "invalid quantity"
        ) from exc

    if quantity <= 0:
        raise InvalidRetailCart(
            "quantity must be greater than zero"
        )

    return quantity


@require_GET
def navbar_cart_fragment(
    request: HttpRequest,
):
    cart = _get_request_cart(
        request
    )

    navbar_cart = (
        build_retail_navbar_cart(
            cart=cart,
        )
    )

    return render(
        request,
        "includes/navbar_cart.html",
        {
            "navbar_cart": navbar_cart,
        },
    )


@require_POST
def set_cart_line_quantity(
    request: HttpRequest,
    cart_line_id: int,
):
    cart = _get_request_cart_or_404(
        request
    )

    line = _get_request_cart_line_or_404(
        cart=cart,
        cart_line_id=cart_line_id,
    )

    try:
        quantity = _parse_quantity(
            request.POST.get(
                "quantity"
            )
        )

        updated_line = (
            update_retail_cart_line_quantity(
                cart=cart,
                line=line,
                quantity=quantity,
            )
        )
    except InvalidRetailCart as error:
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
        mark_retail_cart_active(
            request,
            cart_id=cart.id,
        )

        message = _(
            "Quantity updated."
        )

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": True,
                    "message": str(message),
                    "quantity": updated_line.quantity,
                }
            )

        messages.success(
            request,
            message,
        )

    return redirect(
        "storefront:product_list"
    )


@require_POST
def remove_cart_line(
    request: HttpRequest,
    cart_line_id: int,
):
    cart = _get_request_cart_or_404(
        request
    )

    line = _get_request_cart_line_or_404(
        cart=cart,
        cart_line_id=cart_line_id,
    )

    try:
        remove_retail_cart_line(
            cart=cart,
            line=line,
        )
    except InvalidRetailCart as error:
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
        mark_retail_cart_active(
            request,
            cart_id=cart.id,
        )

        message = _(
            "Product removed from your cart."
        )

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": True,
                    "message": str(message),
                }
            )

        messages.success(
            request,
            message,
        )

    return redirect(
        "storefront:product_list"
    )
