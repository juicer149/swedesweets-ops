from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone


RECENT_PORTAL_ORDER_LIMIT = 5


@dataclass(frozen=True, slots=True)
class PortalHomeAction:
    label: str
    href: str
    css_class: str
    aria_label: str
    icon: str


@dataclass(frozen=True, slots=True)
class PortalMetric:
    label: str
    value: str
    subtext: str
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class PortalRecentOrderRow:
    order_id: int
    href: str
    card_class: str
    status_label: str
    status_class: str
    created_at_label: str
    action_label: str


@dataclass(frozen=True, slots=True)
class PortalHomeContext:
    title: str
    title_id: str
    eyebrow: str
    description: str
    customer_email: str
    customer_location: str
    actions: tuple[PortalHomeAction, ...]
    metrics: tuple[PortalMetric, ...]
    recent_orders: tuple[PortalRecentOrderRow, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "title_id": self.title_id,
            "eyebrow": self.eyebrow,
            "description": self.description,
            "customer_email": self.customer_email,
            "customer_location": self.customer_location,
            "actions": self.actions,
            "metrics": self.metrics,
            "recent_orders": self.recent_orders,
        }


def build_portal_home_context(
    *,
    customer,
    order_summary,
    recent_orders,
) -> PortalHomeContext:
    in_progress_orders = (
        order_summary.placed_orders
        + order_summary.packed_orders
    )

    return PortalHomeContext(
        title=f"Welcome back, {customer.name}",
        title_id="customer-portal-title",
        eyebrow="Customer portal",
        description=(
            "Place new orders, review your order history, "
            "and follow recent activity."
        ),
        customer_email=customer.email,
        customer_location=_customer_location_label(customer),
        actions=_build_home_actions(),
        metrics=(
            PortalMetric(
                label="Total orders",
                value=str(order_summary.total_orders),
                subtext="All orders placed with SwedeSweets",
            ),
            PortalMetric(
                label="In progress",
                value=str(in_progress_orders),
                subtext="Placed or packed orders",
                tone="info",
            ),
            PortalMetric(
                label="Delivered",
                value=str(order_summary.delivered_orders),
                subtext="Completed deliveries",
                tone="success",
            ),
            PortalMetric(
                label="Last order",
                value=_optional_date_label(order_summary.last_ordered_at),
                subtext="Most recent order date",
                tone="muted",
            ),
        ),
        recent_orders=tuple(
            _recent_order_row(order)
            for order in recent_orders
        ),
    )


def _build_home_actions() -> tuple[PortalHomeAction, ...]:
    return (
        PortalHomeAction(
            label="Place order",
            href=reverse("customer_portal:place_order"),
            css_class=(
                "button button--hero-action button--tone-place "
                "button--with-icon"
            ),
            aria_label="Place a new customer order",
            icon="cart",
        ),
        PortalHomeAction(
            label="Order history",
            href=reverse("customer_portal:orders"),
            css_class=(
                "button button--hero-action button--tone-pack "
                "button--with-icon"
            ),
            aria_label="View your order history",
            icon="packed",
        ),
    )


def _recent_order_row(order) -> PortalRecentOrderRow:
    tone = _order_status_tone(order.status)

    return PortalRecentOrderRow(
        order_id=order.pk,
        href=reverse(
            "customer_portal:order_detail",
            kwargs={"order_id": order.pk},
        ),
        card_class=(
            "mobile-card mobile-card--clickable "
            f"mobile-card--{tone} portal-order-item"
        ),
        status_label=order.get_status_display(),
        status_class=f"status-text status-text--{order.status}",
        created_at_label=_datetime_label(order.created_at),
        action_label="View order →",
    )


def _order_status_tone(status: str) -> str:
    return {
        "placed": "warning",
        "packed": "info",
        "delivered": "success",
        "cancelled": "danger",
    }.get(status, "neutral")


def _customer_location_label(customer) -> str:
    location = ", ".join(
        part
        for part in (customer.city, customer.country_name)
        if part
    )

    if location:
        return location

    return "No location added"


def _optional_date_label(value: datetime | None) -> str:
    if value is None:
        return "Never"

    return timezone.localtime(value).strftime("%Y-%m-%d")


def _datetime_label(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
