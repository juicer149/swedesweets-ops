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
    cancel_url: str
    form_errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_formset": self.line_formset,
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
            "form_errors": self.form_errors,
        }


def build_portal_place_order_context(
    *,
    line_formset: PortalOrderLineFormSet,
    form_errors: tuple[str, ...] = (),
) -> PortalPlaceOrderContext:
    return PortalPlaceOrderContext(
        line_formset=line_formset,
        title=_("Place order"),
        description=_("Choose products and quantities for your next order."),
        submit_label=_("Place order"),
        cancel_url=reverse("customer_portal:orders"),
        form_errors=form_errors,
    )
