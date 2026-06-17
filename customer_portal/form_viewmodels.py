from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from customer_portal.forms import PortalOrderLineFormSet


@dataclass(frozen=True, slots=True)
class PortalPlaceOrderContext:
    line_formset: PortalOrderLineFormSet
    title: str
    description: str
    submit_label: str
    save_draft_label: str
    discard_draft_label: str
    cancel_url: str
    has_active_draft: bool
    form_errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_formset": self.line_formset,
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "save_draft_label": self.save_draft_label,
            "discard_draft_label": self.discard_draft_label,
            "cancel_url": self.cancel_url,
            "has_active_draft": self.has_active_draft,
            "form_errors": self.form_errors,
        }


def build_portal_place_order_context(
    *,
    line_formset: PortalOrderLineFormSet,
    form_errors: tuple[str, ...] = (),
    has_active_draft: bool = False,
) -> PortalPlaceOrderContext:
    title = _("Continue draft") if has_active_draft else _("Place order")
    return PortalPlaceOrderContext(
        line_formset=line_formset,
        title=title,
        description=_("Choose products and quantities for your next order."),
        submit_label=_("Review order"),
        save_draft_label=_("Save draft"),
        discard_draft_label=_("Discard draft"),
        cancel_url=reverse("accounts:after_login"),
        has_active_draft=has_active_draft,
        form_errors=form_errors,
    )
