from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

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
    order_action_link_class,
    order_card_css_class,
    quantity_label,
)


@dataclass(frozen=True, slots=True)
class PortalOrderPageRow:
    order: Order
    status: StatusPresentation
    detail_href: str
    total_quantity: int
    created_at_label: str
    card: UiCard


def build_portal_orders_page_header(
    *,
    active_draft_order=None,
) -> PageHeader:
    has_active_draft = active_draft_order is not None

    return PageHeader(
        title=_("Order history"),
        title_id="portal-orders-title",
        description=_("Review your orders and follow their current status."),
        action=PageHeaderAction(
            label=(_("Continue draft") if has_active_draft else _("Place order")),
            href=reverse("customer_portal:place_order"),
            icon="cart",
            aria_label=(
                _("Continue your unfinished order")
                if has_active_draft
                else _("Place a new order")
            ),
        ),
    )


def build_portal_order_page_rows(
    *,
    orders: list[Order],
) -> list[PortalOrderPageRow]:
    return [_build_portal_order_page_row(order) for order in orders]


def _build_portal_order_page_row(order: Order) -> PortalOrderPageRow:
    status = build_order_status_presentation(order.status)
    detail_href = _order_detail_href(order)
    total_quantity = getattr(order, "total_quantity", 0)
    created_at_label = _date_label(order.created_at)

    return PortalOrderPageRow(
        order=order,
        status=status,
        detail_href=detail_href,
        total_quantity=total_quantity,
        created_at_label=created_at_label,
        card=_build_order_card(
            order=order,
            status=status,
            detail_href=detail_href,
            total_quantity=total_quantity,
            created_at_label=created_at_label,
        ),
    )


def _build_order_card(
    *,
    order: Order,
    status: StatusPresentation,
    detail_href: str,
    total_quantity: int,
    created_at_label: str,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class=f"{order_card_css_class(order.status)} portal-history-card",
        rows=(
            _build_header_row(order, status),
            _build_meta_row(
                created_at_label=created_at_label,
                total_quantity=total_quantity,
            ),
        ),
        action=UiText(
            text=_("View order →"),
            href=detail_href,
            css_class=(
                f"{order_action_link_class(order.status)} portal-history-card__action"
            ),
        ),
    )


def _build_header_row(order: Order, status: StatusPresentation) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=_("Order #%(order_id)s") % {"order_id": order.pk},
            css_class="ui-card-order-id portal-history-card__title",
        ),
        right=status.text,
    )


def _build_meta_row(
    *,
    created_at_label: str,
    total_quantity: int,
) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=_("%(created_at)s · %(quantity)s")
            % {
                "created_at": created_at_label,
                "quantity": quantity_label(total_quantity),
            },
            css_class="ui-card-order-meta portal-history-card__meta",
        ),
    )


def _order_detail_href(order: Order) -> str:
    return reverse(
        "customer_portal:order_detail",
        kwargs={"order_id": order.pk},
    )


def _date_label(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d")
