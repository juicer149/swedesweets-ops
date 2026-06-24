from __future__ import annotations

from datetime import datetime
from urllib.parse import quote_plus

from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

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

CUSTOMER_ORDER_STATUS_LABEL_BY_STATUS = {
    Order.Status.DRAFT: _("Draft"),
    Order.Status.PLACED: _("Received"),
    Order.Status.PACKED: _("Prepared"),
    Order.Status.DELIVERED: _("Delivered"),
    Order.Status.CANCELLED: _("Cancelled"),
}


def customer_order_status_label(status: str) -> str:
    return CUSTOMER_ORDER_STATUS_LABEL_BY_STATUS.get(
        status,
        order_status_label(status),
    )


def _order_card_class(status: str) -> str:
    return ORDER_CARD_CLASS_BY_STATUS.get(
        status,
        ORDER_CARD_CLASS_BY_STATUS[Order.Status.DRAFT],
    )


def order_card_css_class(status: str) -> str:
    return f"{ORDER_CARD_BASE_CLASS} {_order_card_class(status)}"


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
            prefix=Order.Status.PLACED.label,
            value=order.placed_at,
        )

    if order.status == Order.Status.PACKED and order.packed_at:
        return relative_time_label(
            prefix=Order.Status.PACKED.label,
            value=order.packed_at,
        )

    if order.status == Order.Status.DELIVERED and order.delivered_at:
        return _("Delivered %(date)s") % {
            "date": order.delivered_at.strftime("%Y-%m-%d"),
        }

    if order.status == Order.Status.CANCELLED and order.cancelled_at:
        return _("Cancelled %(date)s") % {
            "date": order.cancelled_at.strftime("%Y-%m-%d"),
        }

    return _("Created %(date)s") % {
        "date": order.created_at.strftime("%Y-%m-%d"),
    }


def relative_time_label(*, prefix: str, value: datetime) -> str:
    elapsed = timesince(value, timezone.now()).split(",")[0]

    return _("%(prefix)s %(elapsed)s ago") % {
        "prefix": prefix,
        "elapsed": elapsed,
    }


def quantity_label(quantity: int) -> str:
    return ngettext(
        "%(count)s unit",
        "%(count)s units",
        quantity,
    ) % {"count": quantity}


def order_product_count(order: Order) -> int:
    annotated_count = getattr(order, "product_count", None)

    if annotated_count is not None:
        return int(annotated_count)

    prefetched_lines = getattr(
        order,
        "_prefetched_objects_cache",
        {},
    ).get("lines")

    if prefetched_lines is not None:
        return len(prefetched_lines)

    return order.lines.count()


def order_total_quantity(order: Order) -> int:
    annotated_quantity = getattr(order, "total_quantity", None)

    if annotated_quantity is not None:
        return int(annotated_quantity)

    prefetched_lines = getattr(
        order,
        "_prefetched_objects_cache",
        {},
    ).get("lines")

    if prefetched_lines is not None:
        return sum(line.quantity_in_units for line in prefetched_lines)

    return sum(line.quantity_in_units for line in order.lines.all())


def order_quantity_label(order: Order) -> str:
    return quantity_label(order_total_quantity(order))


def contents_summary(*, product_count: int, total_quantity: int) -> str:
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


def maps_directions_href(address: str) -> str:
    destination = quote_plus(address)
    return f"https://www.google.com/maps/dir/?api=1&destination={destination}"
