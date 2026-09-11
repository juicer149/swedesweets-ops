from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from business_portal.orders.product_presentation import (
    business_order_line_presentation,
)
from orders.models import Order


@dataclass(frozen=True, slots=True)
class PortalDraftLine:
    order_line_id: int
    product_label: str
    offer_label: str | None
    price_label: str | None
    quantity: int
    quantity_url: str
    remove_url: str


@dataclass(frozen=True, slots=True)
class PortalCurrentOrderContext:
    draft_lines: tuple[PortalDraftLine, ...]
    title: str
    description: str
    submit_label: str
    discard_draft_label: str
    continue_shopping_label: str
    continue_shopping_url: str
    cancel_url: str
    has_active_draft: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "draft_lines": self.draft_lines,
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "discard_draft_label": self.discard_draft_label,
            "continue_shopping_label": self.continue_shopping_label,
            "continue_shopping_url": self.continue_shopping_url,
            "cancel_url": self.cancel_url,
            "has_active_draft": self.has_active_draft,
        }


def build_portal_current_order_context(
    *,
    draft_order: Order | None,
    language_code: str | None = None,
) -> PortalCurrentOrderContext:
    draft_lines = (
        _build_portal_draft_lines(
            order=draft_order,
            language_code=language_code,
        )
        if draft_order is not None
        else ()
    )

    title = (
        _("Continue draft")
        if draft_order is not None
        else _("Place order")
    )

    return PortalCurrentOrderContext(
        draft_lines=draft_lines,
        title=title,
        description=_(
            "Review the products and quantities in your draft order."
        ),
        submit_label=_("Next"),
        discard_draft_label=_("Discard draft"),
        continue_shopping_label=_("Continue shopping"),
        continue_shopping_url=reverse(
            "business_portal:catalog"
        ),
        cancel_url=reverse(
            "accounts:after_login"
        ),
        has_active_draft=draft_order is not None,
    )


def _build_portal_draft_lines(
    *,
    order: Order,
    language_code: str | None,
) -> tuple[PortalDraftLine, ...]:
    lines = (
        order.lines
        .select_related(
            "product",
            "business_offer_selection__commercial_price",
        )
        .order_by("id")
    )

    effective_language_code = (
        language_code or "en"
    )

    draft_lines = []

    for line in lines:
        presentation = (
            business_order_line_presentation(
                line,
                language_code=effective_language_code,
                currency=order.currency,
            )
        )

        draft_lines.append(
            PortalDraftLine(
                order_line_id=line.id,
                product_label=(
                    presentation.catalog_label
                ),
                offer_label=(
                    presentation.offer_label
                ),
                price_label=(
                    presentation.price_label
                ),
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
        )

    return tuple(
        draft_lines
    )
