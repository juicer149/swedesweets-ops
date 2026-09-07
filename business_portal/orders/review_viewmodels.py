from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from business_portal.orders.presentation import (
    contents_summary,
    quantity_label,
)
from business_portal.orders.product_presentation import (
    business_product_catalog_label,
)
from orders.models import Order, OrderLine
from products.models import Product


@dataclass(frozen=True, slots=True)
class PortalOrderReviewLine:
    product: Product
    quantity: int
    quantity_label: str
    catalog_label: str


@dataclass(frozen=True, slots=True)
class PortalOrderReviewContext:
    order: Order
    lines: tuple[PortalOrderReviewLine, ...]
    title: str
    items_summary: str
    place_order_label: str
    back_label: str
    discard_draft_label: str
    back_url: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "lines": self.lines,
            "title": self.title,
            "items_summary": self.items_summary,
            "place_order_label": self.place_order_label,
            "back_label": self.back_label,
            "discard_draft_label": self.discard_draft_label,
            "back_url": self.back_url,
        }


def build_portal_order_review_context(
    *,
    order: Order,
    language_code: str,
) -> PortalOrderReviewContext:
    order_lines = tuple(
        order.lines
        .select_related("product")
        .order_by("id")
    )

    lines = tuple(
        _build_review_line(
            line,
            language_code=language_code,
        )
        for line in order_lines
    )

    product_count = len(lines)
    total_quantity = sum(
        line.quantity
        for line in lines
    )

    return PortalOrderReviewContext(
        order=order,
        lines=lines,
        title=_("Review order"),
        items_summary=contents_summary(
            product_count=product_count,
            total_quantity=total_quantity,
        ),
        place_order_label=_("Place order"),
        back_label=_("Back"),
        discard_draft_label=_("Discard draft"),
        back_url=reverse(
            "business_portal:current_order"
        ),
    )


def _build_review_line(
    line: OrderLine,
    *,
    language_code: str,
) -> PortalOrderReviewLine:
    product = line.product

    return PortalOrderReviewLine(
        product=product,
        quantity=line.quantity_in_units,
        quantity_label=quantity_label(
            line.quantity_in_units
        ),
        catalog_label=business_product_catalog_label(
            product,
            language_code=language_code,
        ),
    )
