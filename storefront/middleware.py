from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from storefront.cart import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    COOKIE_SALT,
    PENDING_COOKIE_ACTION_ATTR,
)


class RetailCartMiddleware:
    """Attach the anonymous retail cart identity to each request.

    Reads and verifies a signed cart-id cookie before the view runs, and
    exposes the result as `request.retail_cart_id` (a UUID, or None when no
    valid cart cookie exists). No database access happens here - this
    middleware only establishes and persists cart *identity*, never cart
    state; whether that id still refers to a real, non-expired RetailCart
    is for the view/service layer to resolve.

    After the view runs, it writes, renews, or clears the cart cookie on
    the response, based on what the view explicitly reported via
    `storefront.cart.mark_retail_cart_created`,
    `storefront.cart.mark_retail_cart_active`, or
    `storefront.cart.clear_retail_cart`. A request that never touches the
    cart leaves the existing cookie exactly as the browser sent it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.retail_cart_id = self._read_cart_id(request)
        setattr(request, PENDING_COOKIE_ACTION_ATTR, None)

        response = self.get_response(request)

        action = getattr(request, PENDING_COOKIE_ACTION_ATTR, None)

        if action is None:
            return response

        action_type, cart_id = action

        if action_type == "persist" and cart_id is not None:
            self._set_cookie(response, cart_id)
        elif action_type == "clear":
            response.delete_cookie(COOKIE_NAME)

        return response

    @staticmethod
    def _read_cart_id(request: HttpRequest) -> UUID | None:
        raw = request.get_signed_cookie(
            COOKIE_NAME,
            salt=COOKIE_SALT,
            default=None,
        )

        if raw is None:
            return None

        try:
            return UUID(raw)
        except ValueError:
            return None

    @staticmethod
    def _set_cookie(response: HttpResponse, cart_id: UUID) -> None:
        response.set_signed_cookie(
            COOKIE_NAME,
            str(cart_id),
            salt=COOKIE_SALT,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG,
        )
