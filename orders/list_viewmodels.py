from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.ui import (
    StatusPresentation,
    UiCard,
    UiCardRow,
    UiText,
)
from orders.models import Order
from orders.presentation import (
    ORDER_ADDRESS_CLASS,
    ORDER_ADDRESS_LINK_CLASS,
    ORDER_BUTTON_DELIVER_CLASS,
    ORDER_BUTTON_PACK_CLASS,
    ORDER_CARD_BASE_CLASS,
    ORDER_DELIVER_LABEL,
    ORDER_DETAILS_LABEL,
    ORDER_ID_CLASS,
    ORDER_META_CLASS,
    ORDER_PACK_LABEL,
    ORDER_TITLE_CLASS,
    build_order_status_presentation,
    maps_directions_href,
    order_action_link_class,
    order_card_class,
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


def build_order_page_rows(orders: list[Order]) -> list[OrderPageRow]:
    return [build_order_page_row(order) for order in orders]


def build_order_page_row(order: Order) -> OrderPageRow:
    status = _order_status(order)
    detail_href = _order_detail_href(order)
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
        ),
    )


def _build_order_card(
    *,
    order: Order,
    status: StatusPresentation,
    detail_href: str,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class=f"{ORDER_CARD_BASE_CLASS} {order_card_class(order.status)}",
        rows=(
            _build_header_row(order, status),
            _build_customer_row(order),
            _build_meta_row(order),
            _build_address_row(order),
        ),
        action=_build_action(order=order, detail_href=detail_href),
    )


def _build_header_row(order: Order, status: StatusPresentation) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=f"#{order.pk}",
            css_class=ORDER_ID_CLASS,
        ),
        right=status.text,
    )


def _build_customer_row(order: Order) -> UiCardRow:
    return UiCardRow(
        center=UiText(
            text=order.customer.name,
            css_class=ORDER_TITLE_CLASS,
        ),
    )


def _build_meta_row(order: Order) -> UiCardRow:
    return UiCardRow(
        center=UiText(
            text=f"{order_lifecycle_label(order)} · {order_quantity_label(order)}",
            css_class=ORDER_META_CLASS,
        ),
    )


def _build_address_row(order: Order) -> UiCardRow:
    if order.status == Order.Status.PACKED:
        return UiCardRow(
            center=UiText(
                text=order.customer.address,
                href=maps_directions_href(order.customer.address),
                css_class=ORDER_ADDRESS_LINK_CLASS,
                target="_blank",
                rel="noopener noreferrer",
                aria_label=f"Open directions to {order.customer.address}",
            ),
        )

    return UiCardRow(
        center=UiText(
            text=order.customer.address,
            css_class=ORDER_ADDRESS_CLASS,
        ),
    )


def _build_action(*, order: Order, detail_href: str) -> UiText:
    if order.status == Order.Status.PLACED:
        return UiText(
            text=ORDER_PACK_LABEL,
            href=_pack_order_href(order),
            css_class=ORDER_BUTTON_PACK_CLASS,
            icon="box",
            icon_class="button__icon",
        )

    if order.status == Order.Status.PACKED:
        return UiText(
            text=ORDER_DELIVER_LABEL,
            href=_deliver_order_href(order),
            css_class=ORDER_BUTTON_DELIVER_CLASS,
            icon="truck",
            icon_class="button__icon",
        )

    return UiText(
        text=ORDER_DETAILS_LABEL,
        href=detail_href,
        css_class=order_action_link_class(order.status),
    )


def _order_status(order: Order) -> StatusPresentation:
    return build_order_status_presentation(order.status)


def _order_detail_href(order: Order) -> str:
    if order.status == Order.Status.PLACED:
        return _pack_order_href(order)

    if order.status == Order.Status.PACKED:
        return _deliver_order_href(order)

    return reverse("orders:detail", kwargs={"order_id": order.pk})


def _pack_order_href(order: Order) -> str:
    return reverse("orders:pack", kwargs={"order_id": order.pk})


def _deliver_order_href(order: Order) -> str:
    return reverse("orders:deliver", kwargs={"order_id": order.pk})
