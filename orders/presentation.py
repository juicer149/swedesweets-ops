from __future__ import annotations

from datetime import datetime
from urllib.parse import quote_plus

from django.utils import timezone
from django.utils.timesince import timesince

from common.ui import (
    StatusPresentation,
    TONE_DANGER,
    TONE_INFO,
    TONE_MUTED,
    TONE_SUCCESS,
    TONE_WARNING,
    UiText,
)
from orders.models import Order


ORDER_CARD_BASE_CLASS = "mobile-card mobile-card--order"

ORDER_ID_CLASS = "ui-card-order-id"
ORDER_TITLE_CLASS = "ui-card-order-customer"
ORDER_META_CLASS = "ui-card-order-meta"
ORDER_ADDRESS_CLASS = "ui-card-order-address"
ORDER_ADDRESS_LINK_CLASS = "ui-card-order-address ui-card-order-address--link"

ORDER_BUTTON_PACK_CLASS = (
    "button button--card-action button--tone-pack button--with-icon"
)
ORDER_BUTTON_DELIVER_CLASS = (
    "button button--card-action button--tone-deliver button--with-icon"
)

ORDER_DETAILS_LABEL = "See details →"
ORDER_PACK_LABEL = "Pack order"
ORDER_DELIVER_LABEL = "Mark delivered"

ORDER_CONFIRM_PACK_LABEL = "Confirm packed"
ORDER_CONFIRM_DELIVER_LABEL = "Confirm delivered"
ORDER_EDIT_LABEL = "Edit order"
ORDER_CANCEL_LABEL = "Cancel order"
ORDER_BACK_TO_ORDERS_LABEL = "Back to orders"
ORDER_BACK_TO_ORDER_LABEL = "Back to order"

ORDER_CARD_CLASS_BY_STATUS = {
    Order.Status.DRAFT: "mobile-card--order-draft",
    Order.Status.PLACED: "mobile-card--order-placed",
    Order.Status.PACKED: "mobile-card--order-packed",
    Order.Status.DELIVERED: "mobile-card--order-delivered",
    Order.Status.CANCELLED: "mobile-card--order-cancelled",
}

ORDER_MOBILE_STATUS_CLASS_BY_STATUS = {
    Order.Status.DRAFT: "ui-card-order-status status-text--muted",
    Order.Status.PLACED: "ui-card-order-status status-text--warning",
    Order.Status.PACKED: "ui-card-order-status status-text--info",
    Order.Status.DELIVERED: "ui-card-order-status status-text--success",
    Order.Status.CANCELLED: "ui-card-order-status status-text--danger",
}

ORDER_DETAIL_STATUS_CLASS_BY_STATUS = {
    Order.Status.DRAFT: "status-text status-text--muted",
    Order.Status.PLACED: "status-text status-text--warning",
    Order.Status.PACKED: "status-text status-text--info",
    Order.Status.DELIVERED: "status-text status-text--success",
    Order.Status.CANCELLED: "status-text status-text--danger",
}

ORDER_STATUS_ICON_BY_STATUS = {
    Order.Status.DRAFT: "cart",
    Order.Status.PLACED: "cart",
    Order.Status.PACKED: "packed",
    Order.Status.DELIVERED: "check",
    Order.Status.CANCELLED: "x",
}

ORDER_STATUS_TONE_BY_STATUS = {
    Order.Status.DRAFT: TONE_MUTED,
    Order.Status.PLACED: TONE_WARNING,
    Order.Status.PACKED: TONE_INFO,
    Order.Status.DELIVERED: TONE_SUCCESS,
    Order.Status.CANCELLED: TONE_DANGER,
}

ORDER_ACTION_LINK_CLASS_BY_STATUS = {
    Order.Status.DELIVERED: "ui-card-order-link status-text--success",
    Order.Status.CANCELLED: "ui-card-order-link status-text--danger",
    Order.Status.DRAFT: "ui-card-order-link status-text--muted",
}

ORDER_DETAIL_CARD_CLASS_BY_STATUS = {
    Order.Status.PLACED: "content-card--placed",
    Order.Status.PACKED: "content-card--pack",
    Order.Status.DELIVERED: "content-card--deliver",
    Order.Status.CANCELLED: "content-card--danger",
}


def order_card_class(status: str) -> str:
    return ORDER_CARD_CLASS_BY_STATUS.get(
        status,
        ORDER_CARD_CLASS_BY_STATUS[Order.Status.DRAFT],
    )


def order_mobile_status_class(status: str) -> str:
    return ORDER_MOBILE_STATUS_CLASS_BY_STATUS.get(
        status,
        ORDER_MOBILE_STATUS_CLASS_BY_STATUS[Order.Status.DRAFT],
    )


def order_detail_status_class(status: str) -> str:
    return ORDER_DETAIL_STATUS_CLASS_BY_STATUS.get(
        status,
        ORDER_DETAIL_STATUS_CLASS_BY_STATUS[Order.Status.DRAFT],
    )


def order_detail_card_class(status: str) -> str:
    return ORDER_DETAIL_CARD_CLASS_BY_STATUS.get(status, "")


def order_status_icon(status: str) -> str:
    return ORDER_STATUS_ICON_BY_STATUS.get(
        status,
        ORDER_STATUS_ICON_BY_STATUS[Order.Status.DRAFT],
    )


def order_status_tone(status: str):
    return ORDER_STATUS_TONE_BY_STATUS.get(
        status,
        ORDER_STATUS_TONE_BY_STATUS[Order.Status.DRAFT],
    )


def order_action_link_class(status: str) -> str:
    return ORDER_ACTION_LINK_CLASS_BY_STATUS.get(
        status,
        "ui-card-order-link",
    )


def order_status_label(status: str) -> str:
    try:
        return Order.Status(status).label
    except ValueError:
        return Order.Status.DRAFT.label


def build_order_status_presentation(status: str) -> StatusPresentation:
    label = order_status_label(status)

    return StatusPresentation(
        value=status,
        label=label,
        tone=order_status_tone(status),
        text=UiText(
            text=label,
            css_class=order_mobile_status_class(status),
            icon=order_status_icon(status),
            icon_class="status-text__icon",
        ),
    )


def order_lifecycle_label(order: Order) -> str:
    if order.status == Order.Status.PLACED and order.placed_at:
        return relative_time_label(
            prefix="Placed",
            value=order.placed_at,
        )

    if order.status == Order.Status.PACKED and order.packed_at:
        return relative_time_label(
            prefix="Packed",
            value=order.packed_at,
        )

    if order.status == Order.Status.DELIVERED and order.delivered_at:
        return order.delivered_at.strftime("Delivered %d-%m-%y")

    if order.status == Order.Status.CANCELLED and order.cancelled_at:
        return order.cancelled_at.strftime("Cancelled %d-%m-%y")

    return order.created_at.strftime("Created %d-%m-%y")


def relative_time_label(*, prefix: str, value: datetime) -> str:
    elapsed = timesince(value, timezone.now()).split(",")[0]
    return f"{prefix} {elapsed} ago"


def boxes_label(boxes: int) -> str:
    return "1 box" if boxes == 1 else f"{boxes} boxes"


def order_boxes_label(order: Order) -> str:
    return boxes_label(getattr(order, "total_boxes", 0))


def contents_summary(*, product_count: int, total_boxes: int) -> str:
    product_label = "product" if product_count == 1 else "products"
    return f"{product_count} {product_label} · {boxes_label(total_boxes)}"


def maps_directions_href(address: str) -> str:
    destination = quote_plus(address)
    return f"https://www.google.com/maps/dir/?api=1&destination={destination}"
