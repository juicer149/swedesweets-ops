from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from orders.models import Order, OrderLine
from orders.presentation import (
    contents_summary,
    quantity_label,
)
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
    description: str
    items_summary: str
    total_quantity_label: str
    place_order_label: str
    edit_order_label: str
    save_draft_label: str
    discard_draft_label: str
    edit_order_url: str
    cancel_url: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "lines": self.lines,
            "title": self.title,
            "description": self.description,
            "items_summary": self.items_summary,
            "total_quantity_label": self.total_quantity_label,
            "place_order_label": self.place_order_label,
            "edit_order_label": self.edit_order_label,
            "save_draft_label": self.save_draft_label,
            "discard_draft_label": self.discard_draft_label,
            "edit_order_url": self.edit_order_url,
            "cancel_url": self.cancel_url,
        }


def build_portal_order_review_context(
    *,
    order: Order,
) -> PortalOrderReviewContext:
    order_lines = tuple(order.lines.select_related("product").order_by("id"))
    lines = tuple(
        _build_review_line(line)
        for line in order_lines
    )
    product_count = len(lines)
    total_quantity = sum(line.quantity for line in lines)

    return PortalOrderReviewContext(
        order=order,
        lines=lines,
        title=_("Review order"),
        description=_("Check your products before placing the order."),
        items_summary=contents_summary(
            product_count=product_count,
            total_quantity=total_quantity,
        ),
        total_quantity_label=quantity_label(total_quantity),
        place_order_label=_("Place order"),
        edit_order_label=_("Edit order"),
        save_draft_label=_("Save draft"),
        discard_draft_label=_("Discard draft"),
        edit_order_url=reverse("customer_portal:place_order"),
        cancel_url=reverse("accounts:after_login"),
    )


def _build_review_line(line: OrderLine) -> PortalOrderReviewLine:
    product = line.product
    line_quantity_label = quantity_label(line.quantity_in_units)

    return PortalOrderReviewLine(
        product=product,
        quantity=line.quantity_in_units,
        quantity_label=line_quantity_label,
        catalog_label=product.catalog_label,
    )
