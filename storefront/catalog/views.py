from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import (
    HttpRequest,
    Http404,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.roles import AccountRole
from products.models import Product
from retail.catalog_selectors import (
    get_retail_catalog_product,
    list_retail_catalog_products,
)
from retail.models import RetailCart
from retail.services import (
    InvalidRetailCart,
    InvalidRetailOrder,
    add_retail_cart_line,
    create_retail_cart,
)
from storefront.cart import (
    mark_retail_cart_active,
    mark_retail_cart_created,
)
from storefront.catalog.detail_viewmodels import (
    build_retail_catalog_product_detail_context,
)
from storefront.catalog.viewmodels import (
    build_retail_catalog_payload,
    build_retail_product_cards,
)


def _is_business_customer(
    request: HttpRequest,
) -> bool:
    """Return whether this request belongs to the business sales channel.

    AccountRole is resolved by the authentication/access middleware before
    the view runs. Storefront uses that established identity rather than
    trying to infer business-customer state itself.
    """

    return (
        getattr(
            request,
            "account_role",
            None,
        )
        == AccountRole.BUSINESS_CUSTOMER
    )


def _wants_json(request: HttpRequest) -> bool:
    return (
        "application/json"
        in request.headers.get("Accept", "")
    )


def _parse_commercial_price_id(
    raw_value: str | None,
) -> int:
    """Parse the selected retail offer from form input.

    Unlike business ordering, retail has no unpriced standard offer, so a
    commercial_price_id is always required here.
    """

    if raw_value is None:
        raise InvalidRetailCart(
            "an offer must be selected"
        )

    value = raw_value.strip()

    if not value:
        raise InvalidRetailCart(
            "an offer must be selected"
        )

    try:
        commercial_price_id = int(value)
    except ValueError as exc:
        raise InvalidRetailCart(
            "invalid retail offer"
        ) from exc

    if commercial_price_id <= 0:
        raise InvalidRetailCart(
            "invalid retail offer"
        )

    return commercial_price_id


def _parse_quantity(raw_value: str | None) -> int:
    if raw_value is None:
        return 1

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


def _resolve_cart(
    request: HttpRequest,
) -> tuple[RetailCart, bool]:
    """Resolve the request's cart, without any cookie side effects.

    request.retail_cart_id only proves the cookie was signed by us - it is
    not a guarantee the RetailCart row still exists (see
    RetailCartMiddleware). A missing cart is treated the same as no cookie
    at all: a fresh cart is created.

    Returns (cart, was_created) so the caller can tell the middleware the
    right thing - but only once the whole operation has actually
    succeeded. Marking the cookie here, before the caller knows whether
    add_retail_cart_line will succeed, would risk persisting a cookie for
    a cart that a later rollback removes.
    """

    cart_id = getattr(
        request,
        "retail_cart_id",
        None,
    )

    if cart_id is not None:
        try:
            cart = RetailCart.objects.get(
                pk=cart_id,
            )
        except RetailCart.DoesNotExist:
            pass
        else:
            return cart, False

    return create_retail_cart(), True


def product_list(request: HttpRequest):
    """Render the public retail catalog.

    Business customers use their own sales channel. The public retail URL
    remains canonical for anonymous visitors and staff browsing the public
    site, while a business customer is sent to the equivalent business
    catalog.
    """

    if _is_business_customer(request):
        return redirect(
            "business_portal:catalog"
        )

    catalog_products = (
        list_retail_catalog_products()
    )

    product_cards = build_retail_product_cards(
        products=catalog_products,
        language_code=request.LANGUAGE_CODE,
    )

    catalog_data = build_retail_catalog_payload(
        product_cards=product_cards,
    )

    return render(
        request,
        "storefront/catalog/index.html",
        {
            "product_cards": product_cards,
            "catalog_data": catalog_data,
        },
    )


def product_detail(
    request: HttpRequest,
    product_id: int,
):
    """Render one currently orderable retail catalog product.

    A business customer is redirected to the same product in the business
    catalog before any retail catalog lookup is performed.
    """

    if _is_business_customer(request):
        return redirect(
            "business_portal:catalog_product",
            product_id=product_id,
        )

    catalog_product = get_retail_catalog_product(
        product_id=product_id,
    )

    if catalog_product is None:
        raise Http404(
            "Product is not available in the retail catalog."
        )

    context = build_retail_catalog_product_detail_context(
        catalog_product=catalog_product,
        language_code=request.LANGUAGE_CODE,
    )

    return render(
        request,
        "storefront/catalog/detail.html",
        context.as_dict(),
    )


@require_POST
def add_to_cart(
    request: HttpRequest,
    product_id: int,
):
    if _is_business_customer(request):
        message = _(
            "Retail cart actions are not available "
            "for business customers."
        )

        if _wants_json(request):
            return JsonResponse(
                {
                    "ok": False,
                    "message": message,
                },
                status=403,
            )

        return HttpResponseForbidden(
            message
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

        quantity = _parse_quantity(
            request.POST.get("quantity")
        )

        with transaction.atomic():
            cart, cart_was_created = (
                _resolve_cart(request)
            )

            add_retail_cart_line(
                cart=cart,
                commercial_price_id=commercial_price_id,
                quantity=quantity,
            )
    except (
        InvalidRetailCart,
        InvalidRetailOrder,
    ) as error:
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
        # Only now that the line has actually been added do we tell the
        # middleware to persist or renew the cart cookie - a rollback
        # above must never leave a cookie pointing at a cart that no
        # longer exists.
        if cart_was_created:
            mark_retail_cart_created(
                request,
                cart_id=cart.id,
            )
        else:
            mark_retail_cart_active(
                request,
                cart_id=cart.id,
            )

        message = _(
            "%(product)s added to your cart."
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
        "storefront:product_list"
    )
