from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from accounts.roles import RoleSpec
from orders.access import can_cancel_order
from orders.detail_viewmodels import (
    build_order_cancel_back_url,
    build_order_detail_context,
    order_cancel_href,
    order_detail_href,
)
from orders.forms import (
    OrderCancelForm,
    OrderCreateForm,
    OrderLineFormSet,
)
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
    cancel_order_url: str = ""

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
            "cancel_order_url": self.cancel_order_url,
        }


@dataclass(frozen=True)
class CancelOrderFormContext:
    order: Order
    form: OrderCancelForm
    title: str
    description: str
    submit_label: str
    cancel_url: str

    def as_dict(self) -> dict[str, Any]:
        context = build_order_detail_context(
            order=self.order,
            title=self.title,
            description=self.description,
            cancel_url=self.cancel_url,
            active_panel="order",
            include_contents=True,
        ).as_dict()

        context["form"] = self.form
        context["submit_label"] = self.submit_label

        return context


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
    role_spec: RoleSpec,
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
        cancel_url=order_detail_href(order),
        is_edit=True,
        cancel_order_url=(
            order_cancel_href(order)
            if can_cancel_order(order=order, role_spec=role_spec)
            else ""
        ),
    )


def build_cancel_order_form_context(
    *,
    order: Order,
    form: OrderCancelForm,
    role_spec: RoleSpec,
) -> CancelOrderFormContext:
    return CancelOrderFormContext(
        order=order,
        form=form,
        title=f"Cancel order #{order.id}",
        description="",
        submit_label="Cancel order",
        cancel_url=build_order_cancel_back_url(
            order=order,
            role_spec=role_spec,
        ),
    )
