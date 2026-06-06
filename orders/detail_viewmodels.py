from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import Capability, RoleSpec
from common.detail_cards import (
    ACTION_METHOD_GET,
    ACTION_METHOD_POST,
    ACTION_TONE_DELIVER,
    ACTION_TONE_PACK,
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_danger_get_action,
    build_secondary_get_action,
)
from common.ui import UiCard
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
from products.mini_cards import build_product_quantity_mini_card
from products.models import Product


@dataclass(frozen=True)
class OrderContentLine:
    product: Product
    product_detail_href: str
    quantity: int
    quantity_label: str
    unit: str
    catalog_label: str
    card: UiCard


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
        customer_maps_href=maps_directions_href(order.customer_address),
        customer_detail_href=customer_detail_href(order),
        pick_lines=pick_lines,
    )


def build_order_detail_primary_action(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> DetailAction | None:
    if (
        order.status == Order.Status.PLACED
        and role_spec.allows(Capability.PACK_ORDERS)
    ):
        return build_go_to_pack_action(
            href=reverse("orders:pack", kwargs={"order_id": order.id}),
        )

    if (
        order.status == Order.Status.PACKED
        and role_spec.allows(Capability.DELIVER_ORDERS)
    ):
        return build_go_to_deliver_action(
            href=reverse("orders:deliver", kwargs={"order_id": order.id}),
        )

    return None


def build_order_secondary_actions(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> tuple[DetailAction, ...]:
    actions: list[DetailAction] = []

    if can_edit_order(order=order, role_spec=role_spec):
        actions.append(
            build_edit_order_action(
                href=reverse("orders:edit", kwargs={"order_id": order.id}),
            )
        )

    if can_cancel_order(order=order, role_spec=role_spec):
        actions.append(
            build_cancel_order_action(
                href=reverse("orders:cancel", kwargs={"order_id": order.id}),
            )
        )

    return tuple(actions)


def build_order_cancel_back_url(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> str:
    if can_edit_order(order=order, role_spec=role_spec):
        return reverse("orders:edit", kwargs={"order_id": order.id})

    if (
        order.status == Order.Status.PLACED
        and role_spec.allows(Capability.PACK_ORDERS)
    ):
        return reverse("orders:pack", kwargs={"order_id": order.id})

    return reverse("orders:detail", kwargs={"order_id": order.id})


def build_post_edit_success_url(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> str:
    if (
        order.status == Order.Status.PLACED
        and role_spec.allows(Capability.PACK_ORDERS)
    ):
        return reverse("orders:pack", kwargs={"order_id": order.id})

    return reverse("orders:detail", kwargs={"order_id": order.id})


def build_post_pack_success_url(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> str:
    if (
        order.status == Order.Status.PACKED
        and role_spec.allows(Capability.DELIVER_ORDERS)
    ):
        return reverse("orders:deliver", kwargs={"order_id": order.id})

    return reverse("orders:detail", kwargs={"order_id": order.id})


def can_edit_order(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> bool:
    return (
        order.can_be_edited
        and role_spec.allows(Capability.EDIT_ORDERS)
    )


def can_cancel_order(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> bool:
    return (
        order.can_be_cancelled
        and role_spec.allows(Capability.CANCEL_ORDERS)
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
    return build_secondary_get_action(
        label=ORDER_EDIT_LABEL,
        href=href,
    )


def build_cancel_order_action(*, href: str) -> DetailAction:
    return build_danger_get_action(
        label=ORDER_CANCEL_LABEL,
        href=href,
        icon="x",
    )


def _build_order_header(order: Order) -> DetailHeader:
    return DetailHeader(
        eyebrow="Customer",
        title=order.customer_name,
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
            summary=order.customer_name,
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
    content_lines: list[OrderContentLine] = []

    for line in lines:
        product_detail_href = reverse(
            "products:detail",
            kwargs={"product_pk": line.product_id},
        )
        quantity_text = line.product.stock_quantity_label(line.quantity_in_units)

        content_lines.append(
            OrderContentLine(
                product=line.product,
                product_detail_href=product_detail_href,
                quantity=line.quantity_in_units,
                quantity_label=quantity_text,
                unit=line.get_unit_display(),
                catalog_label=line.product.catalog_label,
                card=build_product_quantity_mini_card(
                    product=line.product,
                    product_href=product_detail_href,
                    quantity_label=quantity_text,
                ),
            )
        )

    return content_lines
