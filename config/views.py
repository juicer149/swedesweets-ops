from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from common.dashboard import (
    DashboardAction,
    DashboardMetric,
    DashboardSummaryCard,
)
from common.ui import (
    TONE_DANGER,
    TONE_INFO,
    TONE_SUCCESS,
    TONE_WARNING,
)
from inventory.selectors import (
    count_expiring_batches,
    count_low_stock_products,
)
from orders.models import Order
from orders.selectors import (
    count_packed_orders,
    count_placed_orders,
)


LOW_STOCK_THRESHOLD = 20
DASHBOARD_EXPIRING_DAYS = 45


@login_required
def index(request):
    placed_count = count_placed_orders()
    packed_count = count_packed_orders()
    expiring_count = count_expiring_batches()
    low_stock_count = count_low_stock_products(threshold=LOW_STOCK_THRESHOLD)

    orders_url = reverse("orders:index")
    inventory_url = reverse("inventory:index")

    context = {
        "dashboard_actions": [
            DashboardAction(
                label="Place",
                href=reverse("orders:create"),
                css_class=(
                    "button button--hero-action "
                    "button--tone-place button--with-icon"
                ),
                aria_label="Place a new order",
                icon="cart",
            ),
            DashboardAction(
                label="Pack",
                href=f"{orders_url}?status={Order.Status.PLACED}#orders-list",
                css_class=(
                    "button button--hero-action "
                    "button--tone-pack button--with-icon"
                ),
                aria_label="View placed orders waiting to be packed",
                icon="box",
            ),
            DashboardAction(
                label="Deliver",
                href=f"{orders_url}?status={Order.Status.PACKED}#orders-list",
                css_class=(
                    "button button--hero-action "
                    "button--tone-deliver button--with-icon"
                ),
                aria_label="View packed orders ready for delivery",
                icon="truck",
            ),
        ],
        "dashboard_metrics": [
            DashboardMetric(
                value=placed_count,
                label="waiting to be packed",
                tone="pack",
            ),
            DashboardMetric(
                value=packed_count,
                label="ready for delivery",
                tone="deliver",
            ),
        ],
        "summary_cards": [
            DashboardSummaryCard(
                title="Placed orders",
                count=placed_count,
                description=_pluralize(
                    placed_count,
                    singular="order waiting to be packed",
                    plural="orders waiting to be packed",
                ),
                href=f"{orders_url}?status={Order.Status.PLACED}#orders-list",
                action_label="Manage →",
                tone=TONE_WARNING,
                empty_text="No placed orders waiting.",
                icon="cart",
            ),
            DashboardSummaryCard(
                title="Packed orders",
                count=packed_count,
                description=_pluralize(
                    packed_count,
                    singular="order ready for delivery",
                    plural="orders ready for delivery",
                ),
                href=f"{orders_url}?status={Order.Status.PACKED}#orders-list",
                action_label="Manage →",
                tone=TONE_INFO,
                empty_text="No packed orders ready.",
                icon="packed",
            ),
            DashboardSummaryCard(
                title="Expiring batches",
                count=expiring_count,
                description=_pluralize(
                    expiring_count,
                    singular=(
                        f"batch expiring in the next "
                        f"{DASHBOARD_EXPIRING_DAYS} days"
                    ),
                    plural=(
                        f"batches expiring in the next "
                        f"{DASHBOARD_EXPIRING_DAYS} days"
                    ),
                ),
                href=f"{inventory_url}?sort=best_before#inventory-list",
                action_label="View →",
                tone=TONE_DANGER if expiring_count else TONE_SUCCESS,
                empty_text="No batches expiring soon.",
                icon="warning",
            ),
            DashboardSummaryCard(
                title="Low stock",
                count=low_stock_count,
                description=_pluralize(
                    low_stock_count,
                    singular="product running low",
                    plural="products running low",
                ),
                href=f"{inventory_url}#inventory-list",
                action_label="View →",
                tone=TONE_WARNING if low_stock_count else TONE_SUCCESS,
                empty_text="No low stock products.",
                icon="inventory",
            ),
        ],
    }

    return render(request, "index.html", context)


def _pluralize(
    count: int,
    *,
    singular: str,
    plural: str,
) -> str:
    if count == 1:
        return singular

    return plural
