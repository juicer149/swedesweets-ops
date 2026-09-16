from __future__ import annotations

from uuid import UUID

from django.http import HttpRequest


COOKIE_NAME = "retail_cart"
COOKIE_SALT = "storefront.retail_cart"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


# Internal contract between this module and RetailCartMiddleware. Not part
# of the public storefront.cart API - view code should call the functions
# below, never set this attribute directly.
PENDING_COOKIE_ACTION_ATTR = "_retail_cart_cookie_action"


def mark_retail_cart_created(
    request: HttpRequest,
    *,
    cart_id: UUID,
) -> None:
    """Record that a new anonymous retail cart was created this request.

    RetailCartMiddleware persists this as a fresh, full-TTL cart cookie on
    the outgoing response.
    """

    request.retail_cart_id = cart_id

    setattr(
        request,
        PENDING_COOKIE_ACTION_ATTR,
        ("persist", cart_id),
    )


def mark_retail_cart_active(
    request: HttpRequest,
    *,
    cart_id: UUID,
) -> None:
    """Record that an existing retail cart was used or mutated this request.

    RetailCartMiddleware renews the cart cookie's TTL on the outgoing
    response without changing which cart it identifies.
    """

    setattr(
        request,
        PENDING_COOKIE_ACTION_ATTR,
        ("persist", cart_id),
    )


def clear_retail_cart(request: HttpRequest) -> None:
    """Record that the retail cart cookie should be cleared.

    Used once a cart has been consumed - for example converted into a
    checkout and deleted - so a stale cart id is never persisted back to
    the browser.
    """

    request.retail_cart_id = None

    setattr(
        request,
        PENDING_COOKIE_ACTION_ATTR,
        ("clear", None),
    )
