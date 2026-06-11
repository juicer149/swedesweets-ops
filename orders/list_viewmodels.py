from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import Capability, RoleSpec
from common.page_header import PageHeader, PageHeaderAction
from common.ui import (
    StatusPresentation,
    UiCard,
    UiCardRow,
    UiText,
)
from orders.models import Order
from orders.presentation import (
    build_order_status_presentation,
    maps_directions_href,
    order_action_link_class,
    order_card_css_class,
    order_lifecycle_label,
    order_quantity_label,
)


@dataclass(frozen=True)
class OrderPageRow:
    order: Order
    status: StatusPresentation
    detail_href: str
    total_quantity: int
    card: UiCard


def build_orders_page_header(*, role_spec: RoleSpec) -> PageHeader:
    return PageHeader(
        title="Orders",
        title_id="orders-title",
        action=_build_create_order_header_action(role_spec),
    )


def build_order_page_rows(
    *,
    orders: list[Order],
    role_spec: RoleSpec,
) -> list[OrderPageRow]:
    return [
        build_order_page_row(
            order=order,
            role_spec=role_spec,
        )
        for order in orders
    ]


def build_order_page_row(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> OrderPageRow:
    status = _order_status(order)
    detail_href = _order_detail_href(
        order=order,
        role_spec=role_spec,
    )
    total_quantity = getattr(order, "total_quantity", 0)

    return OrderPageRow(
        order=order,
        status=status,
        detail_href=detail_href,
        total_quantity=total_quantity,
        card=_build_order_card(
            order=order,
            status=status,
            detail_href=detail_href,
            role_spec=role_spec,
        ),
    )


def _build_create_order_header_action(
    role_spec: RoleSpec,
) -> PageHeaderAction | None:
    if not role_spec.allows(Capability.CREATE_ORDERS):
        return None

    return PageHeaderAction(
        label="Place order",
        href=reverse("orders:create"),
        icon="cart",
        aria_label="Place a new order",
    )


def _build_order_card(
    *,
    order: Order,
    status: StatusPresentation,
    detail_href: str,
    role_spec: RoleSpec,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class=order_card_css_class(order.status),
        rows=(
            _build_header_row(order, status),
            _build_customer_row(order),
            _build_meta_row(order),
            _build_address_row(order),
        ),
        action=_build_action(
            order=order,
            detail_href=detail_href,
            role_spec=role_spec,
        ),
    )


def _build_header_row(order: Order, status: StatusPresentation) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=f"#{order.pk}",
            css_class="ui-card-order-id",
        ),
        right=status.text,
    )


def _build_customer_row(order: Order) -> UiCardRow:
    return UiCardRow(
        center=UiText(
            text=order.customer_name,
            css_class="ui-card-order-customer",
        ),
    )


def _build_meta_row(order: Order) -> UiCardRow:
    return UiCardRow(
        center=UiText(
            text=f"{order_lifecycle_label(order)} · {order_quantity_label(order)}",
            css_class="ui-card-order-meta",
        ),
    )


def _build_address_row(order: Order) -> UiCardRow:
    if order.status == Order.Status.PACKED:
        return UiCardRow(
            center=UiText(
                text=order.customer_address,
                href=maps_directions_href(order.customer_address),
                css_class="ui-card-order-address ui-card-order-address--link",
                target="_blank",
                rel="noopener noreferrer",
                aria_label=f"Open directions to {order.customer_address}",
            ),
        )

    return UiCardRow(
        center=UiText(
            text=order.customer_address,
            css_class="ui-card-order-address",
        ),
    )


def _build_action(
    *,
    order: Order,
    detail_href: str,
    role_spec: RoleSpec,
) -> UiText:
    if (
        order.status == Order.Status.PLACED
        and role_spec.allows(Capability.PACK_ORDERS)
    ):
        return UiText(
            text="Pack order",
            href=_pack_order_href(order),
            css_class=(
                "button button--card-action "
                "button--tone-pack "
                "button--with-icon"
                ),
            icon="box",
            icon_class="button__icon",
        )

    if (
        order.status == Order.Status.PACKED
        and role_spec.allows(Capability.DELIVER_ORDERS)
    ):
        return UiText(
            text="Mark delivered",
            href=_deliver_order_href(order),
            css_class=(
                "button button--card-action "
                "button--tone-deliver "
                "button--with-icon"
            ),
            icon="truck",
            icon_class="button__icon",
        )

    return UiText(
        text="See details →",
        href=detail_href,
        css_class=order_action_link_class(order.status),
    )


def _order_status(order: Order) -> StatusPresentation:
    return build_order_status_presentation(order.status)


def _order_detail_href(
    *,
    order: Order,
    role_spec: RoleSpec,
) -> str:
    if (
        order.status == Order.Status.PLACED
        and role_spec.allows(Capability.PACK_ORDERS)
    ):
        return _pack_order_href(order)

    if (
        order.status == Order.Status.PACKED
        and role_spec.allows(Capability.DELIVER_ORDERS)
    ):
        return _deliver_order_href(order)

    return reverse("orders:detail", kwargs={"order_id": order.pk})


def _pack_order_href(order: Order) -> str:
    return reverse("orders:pack", kwargs={"order_id": order.pk})


def _deliver_order_href(order: Order) -> str:
    return reverse("orders:deliver", kwargs={"order_id": order.pk})
