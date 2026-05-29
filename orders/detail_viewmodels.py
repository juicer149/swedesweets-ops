from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.detail_cards import (
    ACTION_METHOD_GET,
    ACTION_METHOD_POST,
    ACTION_TONE_DANGER,
    ACTION_TONE_DELIVER,
    ACTION_TONE_PACK,
    ACTION_TONE_SECONDARY,
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
)
from orders.datatypes import PickLine
from orders.models import Order, OrderLine
from orders.presentation import (
    ORDER_CANCEL_LABEL,
    ORDER_CONFIRM_DELIVER_LABEL,
    ORDER_CONFIRM_PACK_LABEL,
    ORDER_DELIVER_LABEL,
    ORDER_EDIT_LABEL,
    ORDER_PACK_LABEL,
    contents_summary,
    maps_directions_href,
    order_detail_card_class,
    order_detail_status_class,
    order_status_icon,
    quantity_label,
)
from products.models import Product


@dataclass(frozen=True)
class OrderContentLine:
    product: Product
    product_detail_href: str
    quantity: int
    quantity_label: str
    unit: str
    catalog_label: str


@dataclass(frozen=True)
class OrderDetailContext:
    order: Order
    content_lines: list[OrderContentLine]
    product_count: int
    total_quantity: int
    total_quantity_label: str
    detail_card: DetailCard
    title: str
    description: str
    cancel_url: str
    customer_maps_href: str
    customer_detail_href: str
    pick_lines: list[PickLine] | None = None

    def as_dict(self) -> dict[str, object]:
        context: dict[str, object] = {
            "order": self.order,
            "content_lines": self.content_lines,
            "product_count": self.product_count,
            "total_quantity": self.total_quantity,
            "total_quantity_label": self.total_quantity_label,
            "detail_card": self.detail_card,
            "title": self.title,
            "description": self.description,
            "cancel_url": self.cancel_url,
            "customer_maps_href": self.customer_maps_href,
            "customer_detail_href": self.customer_detail_href,
        }

        if self.pick_lines is not None:
            context["pick_lines"] = self.pick_lines

        return context


def build_order_detail_context(
    *,
    order: Order,
    title: str,
    description: str,
    cancel_url: str,
    active_panel: str,
    include_contents: bool,
    primary_action: DetailAction | None = None,
    secondary_action: DetailAction | None = None,
    secondary_actions: tuple[DetailAction, ...] = (),
    pick_lines: list[PickLine] | None = None,
) -> OrderDetailContext:
    order_lines = list(order.lines.select_related("product").all())
    content_lines = _build_content_lines(order_lines)
    product_count = len(content_lines)
    total_quantity = sum(line.quantity for line in content_lines)

    return OrderDetailContext(
        order=order,
        content_lines=content_lines,
        product_count=product_count,
        total_quantity=total_quantity,
        total_quantity_label=quantity_label(total_quantity),
        detail_card=DetailCard(
            header=_build_order_header(order),
            panels=_build_order_detail_panels(
                order=order,
                product_count=product_count,
                total_quantity=total_quantity,
                active_panel=active_panel,
                include_contents=include_contents,
            ),
            content_card_class=order_detail_card_class(order.status),
            primary_action=primary_action,
            secondary_action=secondary_action,
            secondary_actions=secondary_actions,
        ),
        title=title,
        description=description,
        cancel_url=cancel_url,
        customer_maps_href=maps_directions_href(order.customer.address),
        customer_detail_href=customer_detail_href(order),
        pick_lines=pick_lines,
    )


def build_go_to_pack_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=ORDER_PACK_LABEL,
        href=href,
        icon="box",
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_PACK,
    )


def build_go_to_deliver_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=ORDER_DELIVER_LABEL,
        href=href,
        icon="truck",
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_DELIVER,
    )


def build_pack_action(*, is_disabled: bool = False) -> DetailAction:
    return DetailAction(
        label=ORDER_CONFIRM_PACK_LABEL,
        icon="box",
        method=ACTION_METHOD_POST,
        tone=ACTION_TONE_PACK,
        client_behavior="pack-checklist",
        is_disabled=is_disabled,
    )


def build_deliver_action() -> DetailAction:
    return DetailAction(
        label=ORDER_CONFIRM_DELIVER_LABEL,
        icon="truck",
        method=ACTION_METHOD_POST,
        tone=ACTION_TONE_DELIVER,
    )


def build_edit_order_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=ORDER_EDIT_LABEL,
        href=href,
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_SECONDARY,
    )


def build_cancel_order_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=ORDER_CANCEL_LABEL,
        href=href,
        icon="x",
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_DANGER,
    )


def _build_order_header(order: Order) -> DetailHeader:
    return DetailHeader(
        eyebrow="Customer",
        title=order.customer.name,
        status_label=order.get_status_display(),
        status_class=order_detail_status_class(order.status),
        status_icon=order_status_icon(order.status),
    )


def _build_order_detail_panels(
    *,
    order: Order,
    product_count: int,
    total_quantity: int,
    active_panel: str,
    include_contents: bool,
) -> tuple[DetailPanel, ...]:
    panels = [
        DetailPanel(
            key="order",
            label="Order",
            summary=f"#{order.id}",
            body_template="orders/includes/detail_panel_order.html",
            icon="cart",
            is_active=active_panel == "order",
        ),
    ]

    if include_contents:
        panels.append(
            DetailPanel(
                key="contents",
                label="Contents",
                summary=contents_summary(
                    product_count=product_count,
                    total_quantity=total_quantity,
                ),
                body_template="orders/includes/detail_panel_contents.html",
                icon="box",
                is_active=active_panel == "contents",
            )
        )

    panels.append(
        DetailPanel(
            key="customer",
            label="Customer",
            summary=order.customer.name,
            body_template="orders/includes/detail_panel_customer.html",
            icon="users",
            is_active=active_panel == "customer",
        )
    )

    return tuple(panels)


def order_detail_href(order: Order) -> str:
    return reverse("orders:detail", kwargs={"order_id": order.pk})


def customer_detail_href(order: Order) -> str:
    return reverse("customers:detail", kwargs={"customer_pk": order.customer_id})


def _build_content_lines(lines: list[OrderLine]) -> list[OrderContentLine]:
    return [
        OrderContentLine(
            product=line.product,
            product_detail_href=reverse(
                "products:detail",
                kwargs={"product_pk": line.product_id},
            ),
            quantity=line.quantity_in_units,
            quantity_label=line.product.stock_quantity_label(line.quantity_in_units),
            unit=line.get_unit_display(),
            catalog_label=line.product.catalog_label,
        )
        for line in lines
    ]
