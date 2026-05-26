from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.detail_cards import (
    ACTION_METHOD_GET,
    ACTION_TONE_SECONDARY,
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
)
from common.ui import UiCard
from customers.models import Customer
from customers.selectors import CustomerOrderSummary
from orders.mini_cards import build_customer_order_mini_card
from orders.models import Order


CUSTOMER_EDIT_LABEL = "Edit customer"


@dataclass(frozen=True)
class CustomerOrderRow:
    order_id: int
    order_href: str
    status: str
    created_at: object
    boxes: int
    card: UiCard


@dataclass(frozen=True)
class CustomerDetailContext:
    customer: Customer
    order_summary: CustomerOrderSummary
    order_rows: list[CustomerOrderRow]
    detail_card: DetailCard
    title: str
    description: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "customer": self.customer,
            "order_summary": self.order_summary,
            "order_rows": self.order_rows,
            "detail_card": self.detail_card,
            "title": self.title,
            "description": self.description,
            "cancel_url": self.cancel_url,
        }


def build_customer_detail_context(
    *,
    customer: Customer,
    order_summary: CustomerOrderSummary,
    orders: list[Order],
    edit_url: str,
    cancel_url: str,
) -> CustomerDetailContext:
    order_rows = _build_order_rows(orders)

    return CustomerDetailContext(
        customer=customer,
        order_summary=order_summary,
        order_rows=order_rows,
        detail_card=DetailCard(
            header=_build_customer_header(customer),
            panels=_build_customer_detail_panels(
                customer=customer,
                order_summary=order_summary,
            ),
            secondary_actions=(
                build_edit_customer_action(href=edit_url),
            ),
        ),
        title=customer.name,
        description="",
        cancel_url=cancel_url,
    )


def build_edit_customer_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=CUSTOMER_EDIT_LABEL,
        href=href,
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_SECONDARY,
    )


def _build_customer_header(customer: Customer) -> DetailHeader:
    return DetailHeader(
        eyebrow="Customer",
        title=customer.name,
        status_label=customer.country_name,
        status_class="status-text status-text--neutral",
        status_icon="users",
    )


def _build_customer_detail_panels(
    *,
    customer: Customer,
    order_summary: CustomerOrderSummary,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="customer",
            label="Customer",
            summary=customer.name,
            body_template="customers/includes/detail_panel_customer.html",
            icon="users",
            is_active=True,
        ),
        DetailPanel(
            key="orders",
            label="Orders",
            summary=_order_summary_label(order_summary.total_orders),
            body_template="customers/includes/detail_panel_orders.html",
            icon="cart",
        ),
    )


def _build_order_rows(orders: list[Order]) -> list[CustomerOrderRow]:
    rows: list[CustomerOrderRow] = []

    for order in orders:
        order_href = reverse("orders:detail", kwargs={"order_id": order.id})
        boxes = sum(line.quantity_in_boxes for line in order.lines.all())

        rows.append(
            CustomerOrderRow(
                order_id=order.id,
                order_href=order_href,
                status=order.get_status_display(),
                created_at=order.created_at,
                boxes=boxes,
                card=build_customer_order_mini_card(
                    order=order,
                    order_href=order_href,
                    boxes=boxes,
                ),
            )
        )

    return rows


def _order_summary_label(total_orders: int) -> str:
    if total_orders == 1:
        return "1 order"

    return f"{total_orders} orders"
