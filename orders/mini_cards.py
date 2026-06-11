from __future__ import annotations

from common.ui import UiCard, UiCardRow, UiText
from orders.models import Order
from orders.presentation import (
    build_order_status_presentation,
    contents_summary,
    order_card_css_class,
    order_lifecycle_label,
)


def build_order_usage_mini_card(
    *,
    order: Order,
    order_href: str,
    customer_name: str,
    allocation_status: str,
    quantity_label_text: str,
) -> UiCard:
    """Build a compact order card for inventory usage views."""

    status = build_order_status_presentation(order.status)

    return UiCard(
        tone=status.tone,
        css_class=order_card_css_class(order.status),
        href=order_href,
        aria_label=f"View order #{order.pk}",
        footer_hint="Open order →",
        rows=(
            _order_header_row(order=order, status=status),
            UiCardRow(
                left=UiText(
                    text=customer_name,
                    css_class="ui-card-title",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=f"{quantity_label_text} · {allocation_status}",
                    css_class="ui-card-strong",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=order_lifecycle_label(order),
                    css_class="ui-card-muted",
                ),
            ),
        ),
    )


def build_customer_order_mini_card(
    *,
    order: Order,
    order_href: str,
    quantity: int,
) -> UiCard:
    """Build a compact order card for customer detail views."""

    status = build_order_status_presentation(order.status)

    return UiCard(
        tone=status.tone,
        css_class=order_card_css_class(order.status),
        href=order_href,
        aria_label=f"View order #{order.pk}",
        footer_hint="Open order →",
        rows=(
            _order_header_row(order=order, status=status),
            UiCardRow(
                left=UiText(
                    text=contents_summary(
                        product_count=_order_product_count(order),
                        total_quantity=_order_total_quantity(
                            order=order,
                            fallback_quantity=quantity,
                        ),
                    ),
                    css_class="ui-card-title",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=order_lifecycle_label(order),
                    css_class="ui-card-muted",
                ),
            ),
        ),
    )


def _order_header_row(
    *,
    order: Order,
    status,
) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=f"Order #{order.pk}",
            css_class="ui-card-id",
        ),
        right=status.text,
    )




def _order_product_count(order: Order) -> int:
    annotated_count = getattr(order, "product_count", None)

    if annotated_count is not None:
        return int(annotated_count)

    prefetched_lines = getattr(order, "_prefetched_objects_cache", {}).get("lines")

    if prefetched_lines is not None:
        return len(prefetched_lines)

    return order.lines.count()


def _order_total_quantity(
    *,
    order: Order,
    fallback_quantity: int,
) -> int:
    annotated_quantity = getattr(order, "total_quantity", None)

    if annotated_quantity is not None:
        return int(annotated_quantity)

    return fallback_quantity
