from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from orders.forms import OrderCreateForm, OrderLineFormSet
from orders.models import Order


@dataclass(frozen=True)
class OrderFormContext:
    title: str
    description: str
    submit_label: str
    cancel_url: str
    line_formset: OrderLineFormSet
    form: OrderCreateForm | None = None
    order: Order | None = None
    is_edit: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "form": self.form,
            "line_formset": self.line_formset,
            "order": self.order,
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
            "is_edit": self.is_edit,
        }


def build_create_order_form_context(
    *,
    form: OrderCreateForm,
    line_formset: OrderLineFormSet,
) -> OrderFormContext:
    return OrderFormContext(
        form=form,
        line_formset=line_formset,
        title="Place order",
        description="Create an order and reserve available stock.",
        submit_label="Place order",
        cancel_url=reverse("orders:index"),
        is_edit=False,
    )


def build_edit_order_form_context(
    *,
    order: Order,
    line_formset: OrderLineFormSet,
) -> OrderFormContext:
    return OrderFormContext(
        order=order,
        line_formset=line_formset,
        title=f"Edit order #{order.id}",
        description=(
            "Update this placed order before it is packed. "
            "Reservations will be rebuilt."
        ),
        submit_label="Update order",
        cancel_url=reverse("orders:detail", kwargs={"order_id": order.id}),
        is_edit=True,
    )
