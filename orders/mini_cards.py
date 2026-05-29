from __future__ import annotations

from common.ui import UiCard, UiCardRow, UiText
from orders.models import Order
from orders.presentation import (
    ORDER_CARD_BASE_CLASS,
    ORDER_DETAILS_LABEL,
    build_order_status_presentation,
    quantity_label,
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
                    text=f"{quantity_label_text} · {allocation_status}",
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
    quantity: int,
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
                    text=quantity_label(quantity),
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
