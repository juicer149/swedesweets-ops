from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import AccountRole, RoleSpec
from common.dashboard import DashboardAction
from orders.models import Order


MAX_DASHBOARD_ACTIONS = 3


@dataclass(frozen=True, slots=True)
class DashboardActionSpec:
    label: str
    capability: str
    css_tone: str
    aria_label: str
    icon: str
    build_href: Callable[[], str]

    def build(self) -> DashboardAction:
        return DashboardAction(
            label=self.label,
            href=self.build_href(),
            css_class=(
                "button button--hero-action "
                f"{self.css_tone} button--with-icon"
            ),
            aria_label=self.aria_label,
            icon=self.icon,
        )


PLACE_ORDER_ACTION = DashboardActionSpec(
    label="Place",
    capability="can_create_orders",
    css_tone="button--tone-place",
    aria_label="Place a new order",
    icon="cart",
    build_href=lambda: reverse("orders:create"),
)

PACK_ORDERS_ACTION = DashboardActionSpec(
    label="Pack",
    capability="can_pack_orders",
    css_tone="button--tone-pack",
    aria_label="View placed orders waiting to be packed",
    icon="box",
    build_href=lambda: (
        f"{reverse('orders:index')}"
        f"?status={Order.Status.PLACED}#orders-list"
    ),
)

DELIVER_ORDERS_ACTION = DashboardActionSpec(
    label="Deliver",
    capability="can_deliver_orders",
    css_tone="button--tone-deliver",
    aria_label="View packed orders ready for delivery",
    icon="truck",
    build_href=lambda: (
        f"{reverse('orders:index')}"
        f"?status={Order.Status.PACKED}#orders-list"
    ),
)

ADD_BATCH_ACTION = DashboardActionSpec(
    label="Add batch",
    capability="can_create_batches",
    css_tone="button--tone-pack",
    aria_label="Add a new inventory batch",
    icon="inventory",
    build_href=lambda: reverse("inventory:create"),
)


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


def build_dashboard_actions(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> tuple[DashboardAction, ...]:
    candidates = DASHBOARD_ACTIONS_BY_ROLE.get(account_role, ())

    actions = tuple(
        candidate.build()
        for candidate in candidates
        if getattr(role_spec, candidate.capability, False)
    )

    return actions[:MAX_DASHBOARD_ACTIONS]
