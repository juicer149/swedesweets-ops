from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import AccountRole, Capability, RoleSpec
from dashboard.viewmodels import DashboardAction
from orders.models import Order

MAX_DASHBOARD_ACTIONS = 3


# ------------------------------------------------------------------------------
# Action specification


@dataclass(frozen=True, slots=True)
class DashboardActionSpec:
    label: str
    capability: Capability
    css_tone: str
    aria_label: str
    icon: str
    build_href: Callable[[], str]

    def build(self) -> DashboardAction:
        return DashboardAction(
            label=self.label,
            href=self.build_href(),
            css_class=(f"button button--hero-action {self.css_tone} button--with-icon"),
            aria_label=self.aria_label,
            icon=self.icon,
        )


# ------------------------------------------------------------------------------
# Href callbacks


def _place_order_href() -> str:
    return reverse("orders:create")


def _pack_orders_href() -> str:
    return f"{reverse('orders:index')}?status={Order.Status.PLACED}#orders-list"


def _deliver_orders_href() -> str:
    return f"{reverse('orders:index')}?status={Order.Status.PACKED}#orders-list"


def _add_batch_href() -> str:
    return reverse("inventory:create")


# ------------------------------------------------------------------------------
# Available actions
#
# Add new actions here and include them in the appropriate role's tuple in
# DASHBOARD_ACTIONS_BY_ROLE below.


PLACE_ORDER_ACTION = DashboardActionSpec(
    label="Place",
    capability=Capability.CREATE_ORDERS,
    css_tone="button--tone-place",
    aria_label="Place a new order",
    icon="cart",
    build_href=_place_order_href,
)

PACK_ORDERS_ACTION = DashboardActionSpec(
    label="Pack",
    capability=Capability.PACK_ORDERS,
    css_tone="button--tone-pack",
    aria_label="View placed orders waiting to be packed",
    icon="box",
    build_href=_pack_orders_href,
)

DELIVER_ORDERS_ACTION = DashboardActionSpec(
    label="Deliver",
    capability=Capability.DELIVER_ORDERS,
    css_tone="button--tone-deliver",
    aria_label="View packed orders ready for delivery",
    icon="truck",
    build_href=_deliver_orders_href,
)

ADD_BATCH_ACTION = DashboardActionSpec(
    label="Add batch",
    capability=Capability.CREATE_BATCHES,
    css_tone="button--tone-pack",
    aria_label="Add a new inventory batch",
    icon="inventory",
    build_href=_add_batch_href,
)


# ------------------------------------------------------------------------------
# Role-specific action families
#
# This is UX, not authorization. A role may have access to a route without that
# route appearing as a hero action.


STAFF_DASHBOARD_ACTIONS = (
    PLACE_ORDER_ACTION,
    PACK_ORDERS_ACTION,
    DELIVER_ORDERS_ACTION,
)

RESTRICTED_STAFF_DASHBOARD_ACTIONS = (
    PACK_ORDERS_ACTION,
    DELIVER_ORDERS_ACTION,
    ADD_BATCH_ACTION,
)

CUSTOMER_DASHBOARD_ACTIONS: tuple[DashboardActionSpec, ...] = ()


DASHBOARD_ACTIONS_BY_ROLE: dict[
    AccountRole,
    tuple[DashboardActionSpec, ...],
] = {
    AccountRole.OWNER: STAFF_DASHBOARD_ACTIONS,
    AccountRole.FULL_STAFF: STAFF_DASHBOARD_ACTIONS,
    AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_DASHBOARD_ACTIONS,
    AccountRole.CUSTOMER: CUSTOMER_DASHBOARD_ACTIONS,
}


# ------------------------------------------------------------------------------
# Public builder


def build_dashboard_actions(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> tuple[DashboardAction, ...]:
    candidates = DASHBOARD_ACTIONS_BY_ROLE.get(account_role, ())

    actions = tuple(
        candidate.build()
        for candidate in candidates
        if role_spec.allows(candidate.capability)
    )

    return actions[:MAX_DASHBOARD_ACTIONS]
