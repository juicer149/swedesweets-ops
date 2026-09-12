from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from business_portal.orders.presentation import (
    business_order_status_label,
    order_status_tone,
)

RECENT_PORTAL_ORDER_LIMIT = 3


@dataclass(frozen=True, slots=True)
class PortalHomeAction:
    label: str
    href: str
    css_class: str
    aria_label: str


@dataclass(frozen=True, slots=True)
class PortalRecentOrderRow:
    order_id: int
    href: str
    status_label: str
    status_class: str
    created_at_label: str


@dataclass(frozen=True, slots=True)
class PortalHomeContext:
    title: str
    title_id: str
    description: str
    catalog_action: PortalHomeAction
    draft_action: PortalHomeAction | None
    recent_orders: tuple[PortalRecentOrderRow, ...]
    orders_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "title_id": self.title_id,
            "description": self.description,
            "catalog_action": self.catalog_action,
            "draft_action": self.draft_action,
            "recent_orders": self.recent_orders,
            "orders_url": self.orders_url,
        }


def build_portal_home_context(
    *,
    customer,
    recent_orders,
    active_draft_order=None,
) -> PortalHomeContext:
    return PortalHomeContext(
        title=_("Welcome back, %(name)s")
        % {
            "name": customer.name,
        },
        title_id="customer-portal-title",
        description=_(
            "Browse the catalog and keep track of your recent orders."
        ),
        catalog_action=PortalHomeAction(
            label=_("Browse catalog"),
            href=reverse(
                "business_portal:catalog"
            ),
            css_class=(
                "button button--md button--solid "
                "button--tone-place"
            ),
            aria_label=_(
                "Browse the product catalog"
            ),
        ),
        draft_action=_build_draft_action(
            active_draft_order=active_draft_order,
        ),
        recent_orders=tuple(
            _recent_order_row(order)
            for order in recent_orders
        ),
        orders_url=reverse(
            "business_portal:orders"
        ),
    )


def _build_draft_action(
    *,
    active_draft_order=None,
) -> PortalHomeAction | None:
    if active_draft_order is None:
        return None

    return PortalHomeAction(
        label=_("View current order"),
        href=reverse(
            "business_portal:current_order"
        ),
        css_class=(
            "button button--md button--soft "
            "button--tone-place"
        ),
        aria_label=_(
            "View your current order"
        ),
    )


def _recent_order_row(
    order,
) -> PortalRecentOrderRow:
    tone = order_status_tone(
        order.status
    )

    return PortalRecentOrderRow(
        order_id=order.pk,
        href=reverse(
            "business_portal:order_detail",
            kwargs={
                "order_id": order.pk,
            },
        ),
        status_label=business_order_status_label(
            order.status
        ),
        status_class=(
            f"status-text status-text--{order.status}"
        ),
        created_at_label=_datetime_label(
            order.created_at
        ),
    )


def _datetime_label(
    value: datetime,
) -> str:
    return timezone.localtime(
        value
    ).strftime(
        "%Y-%m-%d %H:%M"
    )
