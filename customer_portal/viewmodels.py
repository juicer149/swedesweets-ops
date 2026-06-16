from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


RECENT_PORTAL_ORDER_LIMIT = 5


@dataclass(frozen=True, slots=True)
class PortalHomeAction:
    label: str
    href: str
    css_class: str
    aria_label: str
    icon: str
    help_text: str = ""


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
    active_draft_order=None,
) -> PortalHomeContext:
    in_progress_orders = (
        order_summary.placed_orders
        + order_summary.packed_orders
    )

    return PortalHomeContext(
        title=_("Welcome back, %(name)s") % {"name": customer.name},
        title_id="customer-portal-title",
        eyebrow=_("Customer portal"),
        description=_(
            "Place new orders, review your order history, "
            "and follow recent activity."
        ),
        customer_email=customer.email,
        customer_location=_customer_location_label(customer),
        actions=_build_home_actions(active_draft_order=active_draft_order),
        metrics=(
            PortalMetric(
                label=_("Total orders"),
                value=str(order_summary.total_orders),
                subtext=_("All orders placed with SwedeSweets"),
            ),
            PortalMetric(
                label=_("In progress"),
                value=str(in_progress_orders),
                subtext=_("Placed or packed orders"),
                tone="info",
            ),
            PortalMetric(
                label=_("Delivered"),
                value=str(order_summary.delivered_orders),
                subtext=_("Completed deliveries"),
                tone="success",
            ),
            PortalMetric(
                label=_("Last order"),
                value=_optional_date_label(order_summary.last_ordered_at),
                subtext=_("Most recent order date"),
                tone="muted",
            ),
        ),
        recent_orders=tuple(
            _recent_order_row(order)
            for order in recent_orders
        ),
    )


def _build_home_actions(
    *,
    active_draft_order=None,
) -> tuple[PortalHomeAction, ...]:
    has_active_draft = active_draft_order is not None

    order_action_label = (
        _("Continue draft")
        if has_active_draft
        else _("Place order")
    )
    order_action_aria_label = (
        _("Continue your unfinished order")
        if has_active_draft
        else _("Place a new customer order")
    )
    order_action_help_text = (
        _("You have an unfinished order.")
        if has_active_draft
        else ""
    )

    return (
        PortalHomeAction(
            label=order_action_label,
            href=reverse("customer_portal:place_order"),
            css_class=(
                "button button--hero-action button--tone-place "
                "button--with-icon"
            ),
            aria_label=order_action_aria_label,
            icon="cart",
            help_text=order_action_help_text,
        ),
        PortalHomeAction(
            label=_("Orders"),
            href=reverse("customer_portal:orders"),
            css_class=(
                "button button--hero-action button--tone-pack "
                "button--with-icon"
            ),
            aria_label=_("View your order history"),
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
        action_label=_("View order →"),
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

    return _("No location added")


def _optional_date_label(value: datetime | None) -> str:
    if value is None:
        return _("Never")

    return timezone.localtime(value).strftime("%Y-%m-%d")


def _datetime_label(value: datetime) -> str:
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
