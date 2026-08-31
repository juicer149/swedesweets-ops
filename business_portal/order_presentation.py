from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from common.ui import (
    TONE_DANGER,
    TONE_INFO,
    TONE_MUTED,
    TONE_SUCCESS,
    TONE_WARNING,
    StatusPresentation,
    UiText,
)
from orders.models import Order


ORDER_CARD_BASE_CLASS = "mobile-card mobile-card--order"

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

BUSINESS_ORDER_STATUS_LABEL_BY_STATUS = {
    Order.Status.DRAFT: _("Draft"),
    Order.Status.PLACED: _("Received"),
    Order.Status.PACKED: _("Prepared"),
    Order.Status.DELIVERED: _("Delivered"),
    Order.Status.CANCELLED: _("Cancelled"),
}


def business_order_status_label(status: str) -> str:
    return BUSINESS_ORDER_STATUS_LABEL_BY_STATUS.get(
        status,
        order_status_label(status),
    )


def order_status_label(status: str) -> str:
    try:
        return Order.Status(status).label
    except ValueError:
        return Order.Status.DRAFT.label


def order_card_css_class(status: str) -> str:
    status_class = ORDER_CARD_CLASS_BY_STATUS.get(
        status,
        ORDER_CARD_CLASS_BY_STATUS[Order.Status.DRAFT],
    )
    return f"{ORDER_CARD_BASE_CLASS} {status_class}"


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


def quantity_label(quantity: int) -> str:
    return ngettext(
        "%(count)s unit",
        "%(count)s units",
        quantity,
    ) % {"count": quantity}


def contents_summary(
    *,
    product_count: int,
    total_quantity: int,
) -> str:
    product_label = ngettext(
        "%(count)s product",
        "%(count)s products",
        product_count,
    ) % {"count": product_count}

    quantity_text = quantity_label(total_quantity)

    return _("%(products)s · %(quantity)s") % {
        "products": product_label,
        "quantity": quantity_text,
    }
