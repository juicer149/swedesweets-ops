from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import Capability, RoleSpec
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_secondary_get_action,
)
from common.ui import StatusPresentation, UiCard
from customers.models import Customer
from customers.selectors import CustomerOrderSummary
from orders.mini_cards import build_customer_order_mini_card
from orders.models import Order
from orders.presentation import (
    build_order_status_presentation,
    contents_summary,
    order_lifecycle_label,
    quantity_label,
)


@dataclass(frozen=True)
class CustomerOrderRow:
    order_id: int
    order_href: str
    status: StatusPresentation
    created_at: object
    lifecycle_label: str
    product_count: int
    quantity: int
    quantity_label: str
    contents_label: str
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
    role_spec: RoleSpec,
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
            secondary_actions=build_customer_secondary_actions(
                customer=customer,
                role_spec=role_spec,
            ),
        ),
        title=customer.name,
        description="",
        cancel_url=cancel_url,
    )


def build_customer_secondary_actions(
    *,
    customer: Customer,
    role_spec: RoleSpec,
) -> tuple[DetailAction, ...]:
    if not can_edit_customer(customer=customer, role_spec=role_spec):
        return ()

    return (
        build_edit_customer_action(
            href=reverse("customers:edit", kwargs={"customer_pk": customer.pk}),
        ),
    )


def can_edit_customer(
    *,
    customer: Customer,
    role_spec: RoleSpec,
) -> bool:
    return role_spec.allows(Capability.EDIT_CUSTOMERS)


def build_edit_customer_action(*, href: str) -> DetailAction:
    return build_secondary_get_action(
        label="Edit customer",
        href=href,
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
        status = build_order_status_presentation(order.status)
        product_count = _order_product_count(order)
        quantity = _order_total_quantity(order)
        contents_label = contents_summary(
            product_count=product_count,
            total_quantity=quantity,
        )

        rows.append(
            CustomerOrderRow(
                order_id=order.id,
                order_href=order_href,
                status=status,
                created_at=order.created_at,
                lifecycle_label=order_lifecycle_label(order),
                product_count=product_count,
                quantity=quantity,
                quantity_label=quantity_label(quantity),
                contents_label=contents_label,
                card=build_customer_order_mini_card(
                    order=order,
                    order_href=order_href,
                    quantity=quantity,
                ),
            )
        )

    return rows


def _order_product_count(order: Order) -> int:
    annotated_count = getattr(order, "product_count", None)

    if annotated_count is not None:
        return int(annotated_count)

    prefetched_lines = getattr(order, "_prefetched_objects_cache", {}).get("lines")

    if prefetched_lines is not None:
        return len(prefetched_lines)

    return order.lines.count()


def _order_total_quantity(order: Order) -> int:
    annotated_quantity = getattr(order, "total_quantity", None)

    if annotated_quantity is not None:
        return int(annotated_quantity)

    prefetched_lines = getattr(order, "_prefetched_objects_cache", {}).get("lines")

    if prefetched_lines is not None:
        return sum(line.quantity_in_units for line in prefetched_lines)

    return sum(line.quantity_in_units for line in order.lines.all())


def _order_summary_label(total_orders: int) -> str:
    if total_orders == 1:
        return "1 order"

    return f"{total_orders} orders"
