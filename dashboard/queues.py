from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from django.urls import reverse

from accounts.roles import AccountRole, Capability, RoleSpec
from dashboard.viewmodels import (
    DashboardQueueItem,
    DashboardQueuePanel,
    DashboardQueueTab,
)
from inventory.expiry import EXPIRY_SOON_DAYS
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

QUEUE_PREVIEW_LIMIT = 4


# -----------------------------------------------------------------------------
# Public output
#
# This is the shape consumed by dashboard/views.py. Templates should receive
# ready-to-render tabs and one active panel, not role/capability logic.


@dataclass(frozen=True, slots=True)
class DashboardQueueContext:
    tabs: tuple[DashboardQueueTab, ...]
    panel: DashboardQueuePanel | None


# -----------------------------------------------------------------------------
# Queue specification
#
# A DashboardQueueSpec defines one possible dashboard queue.
#
# AccountRole chooses a queue family.
# RoleSpec filters each queue by capability.
# The generic builder below turns the selected specs into tabs and panels.


@dataclass(frozen=True, slots=True)
class DashboardQueueSpec:
    key: str
    label: str
    capability: Capability
    tone: str
    icon: str

    panel_title: str
    panel_description: str
    view_all_label: str

    count_items: Callable[[], int]
    list_items: Callable[[], Iterable[object]]
    build_item: Callable[[object], DashboardQueueItem]
    build_view_all_href: Callable[[], str]

    def build_tab(self, *, count: int) -> DashboardQueueTab:
        return DashboardQueueTab(
            key=self.key,
            label=self.label,
            count=count,
            href=_dashboard_queue_href(self.key),
            tone=self.tone,
            icon=self.icon,
        )

    def build_panel(self) -> DashboardQueuePanel:
        return DashboardQueuePanel(
            key=self.key,
            title=self.panel_title,
            description=self.panel_description,
            items=tuple(self.build_item(item) for item in self.list_items()),
            view_all_href=self.build_view_all_href(),
            view_all_label=self.view_all_label,
        )


# -----------------------------------------------------------------------------
# Query callbacks
#
# These callbacks keep queue specs readable.
#
# Domain defaults such as EXPIRY_SOON_DAYS and LOW_STOCK_THRESHOLD live in their
# own domains. Dashboard owns only QUEUE_PREVIEW_LIMIT, because that is a UI
# preview concern.


def _list_placed_orders() -> Iterable[object]:
    return list_placed_orders_for_dashboard(limit=QUEUE_PREVIEW_LIMIT)


def _list_packed_orders() -> Iterable[object]:
    return list_packed_orders_for_dashboard(limit=QUEUE_PREVIEW_LIMIT)


def _list_expiring_batches() -> Iterable[object]:
    return list_expiring_batch_rows_for_dashboard(
        limit=QUEUE_PREVIEW_LIMIT,
    )


def _list_low_stock_products() -> Iterable[object]:
    return list_low_stock_products_for_dashboard(
        limit=QUEUE_PREVIEW_LIMIT,
    )


# -----------------------------------------------------------------------------
# View-all href callbacks


def _placed_orders_view_all_href() -> str:
    return f"{reverse('orders:index')}?status={Order.Status.PLACED}#orders-list"


def _packed_orders_view_all_href() -> str:
    return f"{reverse('orders:index')}?status={Order.Status.PACKED}#orders-list"


def _expiring_batches_view_all_href() -> str:
    return f"{reverse('inventory:index')}?sort=best_before#inventory-list"


def _low_stock_products_view_all_href() -> str:
    return f"{reverse('inventory:index')}?view=products&sort=available#inventory-list"


# -----------------------------------------------------------------------------
# Item builders
#
# These functions adapt domain rows/models into DashboardQueueItem viewmodels.


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


# -----------------------------------------------------------------------------
# Available queues
#
# Add new dashboard queues here. Each queue is filtered by capability before it
# can appear in the section nav.


PLACED_ORDERS_QUEUE = DashboardQueueSpec(
    key="placed",
    label="Placed",
    capability=Capability.PACK_ORDERS,
    tone="warning",
    icon="cart",
    panel_title="Placed orders",
    panel_description="Orders waiting to be packed.",
    view_all_label="View all placed orders →",
    count_items=count_placed_orders,
    list_items=_list_placed_orders,
    build_item=_placed_order_item,
    build_view_all_href=_placed_orders_view_all_href,
)

PACKED_ORDERS_QUEUE = DashboardQueueSpec(
    key="packed",
    label="Packed",
    capability=Capability.DELIVER_ORDERS,
    tone="info",
    icon="packed",
    panel_title="Packed orders",
    panel_description="Orders ready for delivery.",
    view_all_label="View all packed orders →",
    count_items=count_packed_orders,
    list_items=_list_packed_orders,
    build_item=_packed_order_item,
    build_view_all_href=_packed_orders_view_all_href,
)

EXPIRING_BATCHES_QUEUE = DashboardQueueSpec(
    key="expiring",
    label="Expiring",
    capability=Capability.VIEW_INVENTORY_RISKS,
    tone="danger",
    icon="warning",
    panel_title="Expiring batches",
    panel_description=f"Batches expiring in the next {EXPIRY_SOON_DAYS} days.",
    view_all_label="View expiring batches →",
    count_items=count_expiring_batches,
    list_items=_list_expiring_batches,
    build_item=_expiring_batch_item,
    build_view_all_href=_expiring_batches_view_all_href,
)

LOW_STOCK_QUEUE = DashboardQueueSpec(
    key="low-stock",
    label="Low stock",
    capability=Capability.VIEW_INVENTORY_RISKS,
    tone="warning",
    icon="inventory",
    panel_title="Low stock",
    panel_description="Products running low.",
    view_all_label="View low stock products →",
    count_items=count_low_stock_products,
    list_items=_list_low_stock_products,
    build_item=_low_stock_item,
    build_view_all_href=_low_stock_products_view_all_href,
)


# -----------------------------------------------------------------------------
# Role-specific queue families
#
# This is UX, not authorization. A role may have access to inventory/products
# while still seeing only order-workflow queues on the dashboard.


OPS_DASHBOARD_QUEUES = (
    PLACED_ORDERS_QUEUE,
    PACKED_ORDERS_QUEUE,
    EXPIRING_BATCHES_QUEUE,
    LOW_STOCK_QUEUE,
)

RESTRICTED_STAFF_DASHBOARD_QUEUES = (
    PLACED_ORDERS_QUEUE,
    PACKED_ORDERS_QUEUE,
)

CUSTOMER_DASHBOARD_QUEUES: tuple[DashboardQueueSpec, ...] = ()


DASHBOARD_QUEUES_BY_ROLE: dict[
    AccountRole,
    tuple[DashboardQueueSpec, ...],
] = {
    AccountRole.OWNER: OPS_DASHBOARD_QUEUES,
    AccountRole.FULL_STAFF: OPS_DASHBOARD_QUEUES,
    AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_DASHBOARD_QUEUES,
    AccountRole.CUSTOMER: CUSTOMER_DASHBOARD_QUEUES,
}


# -----------------------------------------------------------------------------
# Public builder


def build_dashboard_queue_context(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
    requested_queue: str,
) -> DashboardQueueContext:
    candidates = DASHBOARD_QUEUES_BY_ROLE.get(account_role, ())
    queue_specs = _visible_queue_specs(
        candidates=candidates,
        role_spec=role_spec,
    )
    tabs = _build_queue_tabs(queue_specs=queue_specs)
    active_queue = _resolve_active_queue(
        requested_queue=requested_queue,
        tabs=tabs,
    )
    active_tabs = tuple(replace(tab, is_active=tab.key == active_queue) for tab in tabs)

    return DashboardQueueContext(
        tabs=active_tabs,
        panel=_build_active_queue_panel(
            active_queue=active_queue,
            queue_specs=queue_specs,
        ),
    )


# -----------------------------------------------------------------------------
# Builder helpers


def _visible_queue_specs(
    *,
    candidates: tuple[DashboardQueueSpec, ...],
    role_spec: RoleSpec,
) -> tuple[DashboardQueueSpec, ...]:
    return tuple(
        queue_spec
        for queue_spec in candidates
        if role_spec.allows(queue_spec.capability)
    )


def _build_queue_tabs(
    *,
    queue_specs: tuple[DashboardQueueSpec, ...],
) -> tuple[DashboardQueueTab, ...]:
    tabs: list[DashboardQueueTab] = []

    for queue_spec in queue_specs:
        count = queue_spec.count_items()

        if count <= 0:
            continue

        tabs.append(queue_spec.build_tab(count=count))

    return tuple(tabs)


def _resolve_active_queue(
    *,
    requested_queue: str,
    tabs: tuple[DashboardQueueTab, ...],
) -> str:
    if not tabs:
        return ""

    visible_keys = {tab.key for tab in tabs}

    if requested_queue in visible_keys:
        return requested_queue

    return tabs[0].key


def _build_active_queue_panel(
    *,
    active_queue: str,
    queue_specs: tuple[DashboardQueueSpec, ...],
) -> DashboardQueuePanel | None:
    if not active_queue:
        return None

    for queue_spec in queue_specs:
        if queue_spec.key == active_queue:
            return queue_spec.build_panel()

    return None


def _dashboard_queue_href(queue_key: str) -> str:
    return f"{reverse('index')}?queue={queue_key}#dashboard-queue"
