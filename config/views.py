from __future__ import annotations

from dataclasses import replace

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from common.dashboard import (
    DashboardAction,
    DashboardQueueItem,
    DashboardQueuePanel,
    DashboardQueueTab,
)
from inventory.expiry import EXPIRY_SOON_DAYS
from inventory.low_stock import LOW_STOCK_THRESHOLD
from inventory.presentation import (
    batch_quantity_label,
    product_available_quantity_label,
)
from inventory.selectors import (
    count_expiring_batches,
    count_low_stock_products,
    list_expiring_batch_rows_for_dashboard,
    list_low_stock_products_for_dashboard,
)
from orders.models import Order
from orders.presentation import (
    order_lifecycle_label,
    order_quantity_label,
)
from orders.selectors import (
    count_packed_orders,
    count_placed_orders,
    list_packed_orders_for_dashboard,
    list_placed_orders_for_dashboard,
)


QUEUE_PLACED = "placed"
QUEUE_PACKED = "packed"
QUEUE_EXPIRING = "expiring"
QUEUE_LOW_STOCK = "low-stock"

QUEUE_PREVIEW_LIMIT = 3


@login_required
def index(request):
    role_spec = request.role_spec

    placed_count = _count_placed_orders_for_dashboard(role_spec=role_spec)
    packed_count = _count_packed_orders_for_dashboard(role_spec=role_spec)
    expiring_count = _count_expiring_batches_for_dashboard(role_spec=role_spec)
    low_stock_count = _count_low_stock_products_for_dashboard(
        role_spec=role_spec,
    )

    requested_queue = request.GET.get("queue", "")

    queue_tabs = _build_queue_tabs(
        role_spec=role_spec,
        placed_count=placed_count,
        packed_count=packed_count,
        expiring_count=expiring_count,
        low_stock_count=low_stock_count,
    )
    active_queue = _resolve_active_queue(
        requested_queue=requested_queue,
        queue_tabs=queue_tabs,
    )
    queue_tabs = tuple(
        replace(tab, is_active=tab.key == active_queue)
        for tab in queue_tabs
    )

    context = {
        "dashboard_actions": _build_dashboard_actions(role_spec=role_spec),
        "dashboard_queue_tabs": queue_tabs,
        "dashboard_queue_panel": _build_queue_panel(
            active_queue,
            role_spec=role_spec,
        ),
    }

    return render(request, "index.html", context)


def _count_placed_orders_for_dashboard(*, role_spec) -> int:
    if not role_spec.can_pack_orders:
        return 0

    return count_placed_orders()


def _count_packed_orders_for_dashboard(*, role_spec) -> int:
    if not role_spec.can_deliver_orders:
        return 0

    return count_packed_orders()


def _count_expiring_batches_for_dashboard(*, role_spec) -> int:
    if not role_spec.can_view_inventory_risks:
        return 0

    return count_expiring_batches(days=EXPIRY_SOON_DAYS)


def _count_low_stock_products_for_dashboard(*, role_spec) -> int:
    if not role_spec.can_view_inventory_risks:
        return 0

    return count_low_stock_products(threshold=LOW_STOCK_THRESHOLD)


def _build_dashboard_actions(*, role_spec) -> tuple[DashboardAction, ...]:
    orders_url = reverse("orders:index")
    actions: list[DashboardAction] = []

    if role_spec.can_create_orders:
        actions.append(
            DashboardAction(
                label="Place",
                href=reverse("orders:create"),
                css_class=(
                    "button button--hero-action "
                    "button--tone-place button--with-icon"
                ),
                aria_label="Place a new order",
                icon="cart",
            )
        )

    if role_spec.can_pack_orders:
        actions.append(
            DashboardAction(
                label="Pack",
                href=f"{orders_url}?status={Order.Status.PLACED}#orders-list",
                css_class=(
                    "button button--hero-action "
                    "button--tone-pack button--with-icon"
                ),
                aria_label="View placed orders waiting to be packed",
                icon="box",
            )
        )

    if role_spec.can_deliver_orders:
        actions.append(
            DashboardAction(
                label="Deliver",
                href=f"{orders_url}?status={Order.Status.PACKED}#orders-list",
                css_class=(
                    "button button--hero-action "
                    "button--tone-deliver button--with-icon"
                ),
                aria_label="View packed orders ready for delivery",
                icon="truck",
            )
        )

    return tuple(actions)


def _build_queue_tabs(
    *,
    role_spec,
    placed_count: int,
    packed_count: int,
    expiring_count: int,
    low_stock_count: int,
) -> tuple[DashboardQueueTab, ...]:
    candidates = (
        (
            role_spec.can_pack_orders,
            DashboardQueueTab(
                key=QUEUE_PLACED,
                label="Placed",
                count=placed_count,
                href=_dashboard_queue_href(QUEUE_PLACED),
                tone="warning",
                icon="cart",
            ),
        ),
        (
            role_spec.can_deliver_orders,
            DashboardQueueTab(
                key=QUEUE_PACKED,
                label="Packed",
                count=packed_count,
                href=_dashboard_queue_href(QUEUE_PACKED),
                tone="info",
                icon="packed",
            ),
        ),
        (
            role_spec.can_view_inventory_risks,
            DashboardQueueTab(
                key=QUEUE_EXPIRING,
                label="Expiring",
                count=expiring_count,
                href=_dashboard_queue_href(QUEUE_EXPIRING),
                tone="danger",
                icon="warning",
            ),
        ),
        (
            role_spec.can_view_inventory_risks,
            DashboardQueueTab(
                key=QUEUE_LOW_STOCK,
                label="Low stock",
                count=low_stock_count,
                href=_dashboard_queue_href(QUEUE_LOW_STOCK),
                tone="warning",
                icon="inventory",
            ),
        ),
    )

    return tuple(
        tab
        for is_allowed, tab in candidates
        if is_allowed and tab.count > 0
    )


def _resolve_active_queue(
    *,
    requested_queue: str,
    queue_tabs: tuple[DashboardQueueTab, ...],
) -> str:
    if not queue_tabs:
        return ""

    visible_keys = {tab.key for tab in queue_tabs}

    if requested_queue in visible_keys:
        return requested_queue

    return queue_tabs[0].key


def _build_queue_panel(
    active_queue: str,
    *,
    role_spec,
) -> DashboardQueuePanel | None:
    if active_queue == QUEUE_PLACED and role_spec.can_pack_orders:
        return _build_placed_queue_panel()

    if active_queue == QUEUE_PACKED and role_spec.can_deliver_orders:
        return _build_packed_queue_panel()

    if active_queue == QUEUE_EXPIRING and role_spec.can_view_inventory_risks:
        return _build_expiring_queue_panel()

    if active_queue == QUEUE_LOW_STOCK and role_spec.can_view_inventory_risks:
        return _build_low_stock_queue_panel()

    return None


def _build_placed_queue_panel() -> DashboardQueuePanel:
    orders = list_placed_orders_for_dashboard(limit=QUEUE_PREVIEW_LIMIT)
    orders_url = reverse("orders:index")

    return DashboardQueuePanel(
        key=QUEUE_PLACED,
        title="Placed orders",
        description="Orders waiting to be packed.",
        items=tuple(_placed_order_item(order) for order in orders),
        view_all_href=f"{orders_url}?status={Order.Status.PLACED}#orders-list",
        view_all_label="View all placed orders →",
    )


def _build_packed_queue_panel() -> DashboardQueuePanel:
    orders = list_packed_orders_for_dashboard(limit=QUEUE_PREVIEW_LIMIT)
    orders_url = reverse("orders:index")

    return DashboardQueuePanel(
        key=QUEUE_PACKED,
        title="Packed orders",
        description="Orders ready for delivery.",
        items=tuple(_packed_order_item(order) for order in orders),
        view_all_href=f"{orders_url}?status={Order.Status.PACKED}#orders-list",
        view_all_label="View all packed orders →",
    )


def _build_expiring_queue_panel() -> DashboardQueuePanel:
    rows = list_expiring_batch_rows_for_dashboard(limit=QUEUE_PREVIEW_LIMIT)
    inventory_url = reverse("inventory:index")

    return DashboardQueuePanel(
        key=QUEUE_EXPIRING,
        title="Expiring batches",
        description=f"Batches expiring in the next {EXPIRY_SOON_DAYS} days.",
        items=tuple(_expiring_batch_item(row) for row in rows),
        view_all_href=f"{inventory_url}?sort=best_before#inventory-list",
        view_all_label="View expiring batches →",
    )


def _build_low_stock_queue_panel() -> DashboardQueuePanel:
    rows = list_low_stock_products_for_dashboard(
        threshold=LOW_STOCK_THRESHOLD,
        limit=QUEUE_PREVIEW_LIMIT,
    )
    inventory_url = reverse("inventory:index")

    return DashboardQueuePanel(
        key=QUEUE_LOW_STOCK,
        title="Low stock",
        description="Products running low.",
        items=tuple(_low_stock_item(row) for row in rows),
        view_all_href=f"{inventory_url}?view=products&sort=available#inventory-list",
        view_all_label="View low stock products →",
    )


def _placed_order_item(order) -> DashboardQueueItem:
    return DashboardQueueItem(
        title=f"#{order.pk} · {order.customer_name}",
        meta=f"{order_lifecycle_label(order)} · {order_quantity_label(order)}",
        href=reverse("orders:pack", kwargs={"order_id": order.pk}),
        action_label="Pack order →",
        tone="warning",
        icon="cart",
    )


def _packed_order_item(order) -> DashboardQueueItem:
    return DashboardQueueItem(
        title=f"#{order.pk} · {order.customer_name}",
        meta=f"{order_lifecycle_label(order)} · {order_quantity_label(order)}",
        href=reverse("orders:deliver", kwargs={"order_id": order.pk}),
        action_label="Mark delivered →",
        tone="info",
        icon="packed",
    )


def _expiring_batch_item(row) -> DashboardQueueItem:
    batch = row.batch

    return DashboardQueueItem(
        title=f"{batch.batch_id} · {batch.product.display_name}",
        meta=(
            f"{batch_quantity_label(batch)} · "
            f"{row.expiry.label} {batch.best_before:%Y-%m-%d}"
        ),
        href=reverse("inventory:detail", kwargs={"batch_pk": batch.pk}),
        action_label="Open batch →",
        tone="danger",
        icon="warning",
    )


def _low_stock_item(row) -> DashboardQueueItem:
    return DashboardQueueItem(
        title=f"{row.code_label} · {row.product_name}",
        meta=product_available_quantity_label(row),
        href=reverse("products:detail", kwargs={"product_pk": row.product_id}),
        action_label="Open product →",
        tone="warning",
        icon="inventory",
    )


def _dashboard_queue_href(queue_key: str) -> str:
    return f"{reverse('index')}?queue={queue_key}#dashboard-queue"
