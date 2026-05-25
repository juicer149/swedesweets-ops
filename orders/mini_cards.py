from __future__ import annotations

from common.ui import UiCard, UiCardRow, UiText
from orders.models import Order
from orders.presentation import (
    ORDER_CARD_BASE_CLASS,
    ORDER_DETAILS_LABEL,
    boxes_label,
    build_order_status_presentation,
)


def build_order_usage_mini_card(
    *,
    order: Order,
    order_href: str,
    customer_name: str,
    allocation_status: str,
    boxes_label: str,
) -> UiCard:
    status = build_order_status_presentation(order.status)

    return UiCard(
        tone=status.tone,
        css_class=ORDER_CARD_BASE_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=f"#{order.pk}",
                    css_class="ui-card-id",
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=customer_name,
                    css_class="ui-card-title",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=f"{boxes_label} · {allocation_status}",
                    css_class="ui-card-strong ui-card-strong--compact",
                ),
            ),
        ),
        action=UiText(
            text=ORDER_DETAILS_LABEL,
            href=order_href,
            css_class="text-link",
        ),
    )


def build_customer_order_mini_card(
    *,
    order: Order,
    order_href: str,
    boxes: int,
) -> UiCard:
    status = build_order_status_presentation(order.status)

    return UiCard(
        tone=status.tone,
        css_class=ORDER_CARD_BASE_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=f"#{order.pk}",
                    css_class="ui-card-id",
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=boxes_label(boxes),
                    css_class="ui-card-title",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=f"Created {order.created_at:%Y-%m-%d %H:%M}",
                    css_class="ui-card-muted",
                ),
            ),
        ),
        action=UiText(
            text=ORDER_DETAILS_LABEL,
            href=order_href,
            css_class="text-link",
        ),
    )
