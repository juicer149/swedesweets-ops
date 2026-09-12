from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from business_portal.orders.product_presentation import (
    business_order_line_presentation,
)
from common.navbar_cart import (
    NavbarCart,
    NavbarCartLine,
)
from orders.models import Order


def build_business_navbar_cart(
    *,
    draft_order: Order | None,
    language_code: str | None = None,
) -> NavbarCart:
    if draft_order is None:
        return _empty_business_navbar_cart()

    order_lines = tuple(
        draft_order.lines
        .select_related(
            "product",
            "business_offer_selection__commercial_price",
        )
        .order_by("id")
    )

    if not order_lines:
        return _empty_business_navbar_cart()

    effective_language_code = (
        language_code or "en"
    )

    lines = tuple(
        _build_business_navbar_cart_line(
            line=line,
            language_code=effective_language_code,
            currency=draft_order.currency,
        )
        for line in order_lines
    )

    return NavbarCart(
        aria_label=_("Current order"),
        title=_("Current order"),
        line_count=len(lines),
        lines=lines,
        fragment_url=reverse(
            "business_portal:navbar_cart_fragment"
        ),
        proceed_label=_("View order"),
        proceed_url=reverse(
            "business_portal:current_order"
        ),
        empty_message=_(
            "Your order is empty."
        ),
        empty_action_label=_(
            "Browse catalog"
        ),
        empty_action_url=reverse(
            "business_portal:catalog"
        ),
    )


def _empty_business_navbar_cart() -> NavbarCart:
    return NavbarCart(
        aria_label=_("Current order"),
        title=_("Current order"),
        line_count=0,
        lines=(),
        fragment_url=reverse(
            "business_portal:navbar_cart_fragment"
        ),
        proceed_label=_("View order"),
        proceed_url=reverse(
            "business_portal:current_order"
        ),
        empty_message=_(
            "Your order is empty."
        ),
        empty_action_label=_(
            "Browse catalog"
        ),
        empty_action_url=reverse(
            "business_portal:catalog"
        ),
    )


def _build_business_navbar_cart_line(
    *,
    line,
    language_code: str,
    currency: str,
) -> NavbarCartLine:
    presentation = (
        business_order_line_presentation(
            line,
            language_code=language_code,
            currency=currency,
        )
    )

    metadata = tuple(
        value
        for value in (
            presentation.offer_label,
            presentation.price_label,
        )
        if value
    )

    return NavbarCartLine(
        line_id=line.id,
        label=presentation.catalog_label,
        product_url=reverse(
            "business_portal:catalog_product",
            kwargs={
                "product_id": line.product_id,
            },
        ),
        metadata=metadata,
        quantity=line.quantity_in_units,
        quantity_url=reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        remove_url=reverse(
            "business_portal:remove_draft_line",
            kwargs={
                "order_line_id": line.id,
            },
        ),
    )
