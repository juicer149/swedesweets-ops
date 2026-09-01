from __future__ import annotations

from accounts.activity import AccountActivity, AccountActivityKind
from customers.selectors import (
    CustomerActivityKind,
    list_customer_activity_for_actor,
)
from inventory.selectors import (
    InventoryActivityKind,
    list_inventory_activity_for_actor,
)
from orders.selectors import (
    OrderActivityKind,
    list_order_activity_for_actor,
)
from products.selectors import (
    ProductActivityKind,
    list_product_activity_for_actor,
)


ACCOUNT_ACTIVITY_LIMIT = 24


def list_account_activities(*, user) -> tuple[AccountActivity, ...]:
    activities = (
        *_order_activities(user),
        *_product_activities(user),
        *_inventory_activities(user),
        *_customer_activities(user),
    )

    return tuple(
        sorted(
            activities,
            key=lambda activity: activity.occurred_at,
            reverse=True,
        )[:ACCOUNT_ACTIVITY_LIMIT]
    )


def _order_activities(user) -> tuple[AccountActivity, ...]:
    kind_map = {
        OrderActivityKind.PLACED: AccountActivityKind.ORDER_PLACED,
        OrderActivityKind.PACKED: AccountActivityKind.ORDER_PACKED,
        OrderActivityKind.DELIVERED: AccountActivityKind.ORDER_DELIVERED,
        OrderActivityKind.CANCELLED: AccountActivityKind.ORDER_CANCELLED,
        OrderActivityKind.EDITED: AccountActivityKind.ORDER_EDITED,
    }

    return tuple(
        AccountActivity(
            occurred_at=activity.occurred_at,
            kind=kind_map[activity.kind],
            target=activity.order,
        )
        for activity in list_order_activity_for_actor(
            actor=user,
            limit=ACCOUNT_ACTIVITY_LIMIT,
        )
    )


def _product_activities(user) -> tuple[AccountActivity, ...]:
    kind_map = {
        ProductActivityKind.CREATED: AccountActivityKind.PRODUCT_CREATED,
        ProductActivityKind.EDITED: AccountActivityKind.PRODUCT_EDITED,
        ProductActivityKind.ACTIVATED: AccountActivityKind.PRODUCT_ACTIVATED,
        ProductActivityKind.DEACTIVATED: (
            AccountActivityKind.PRODUCT_DEACTIVATED
        ),
    }

    return tuple(
        AccountActivity(
            occurred_at=activity.occurred_at,
            kind=kind_map[activity.kind],
            target=activity.product,
        )
        for activity in list_product_activity_for_actor(
            actor=user,
            limit=ACCOUNT_ACTIVITY_LIMIT,
        )
    )


def _inventory_activities(user) -> tuple[AccountActivity, ...]:
    kind_map = {
        InventoryActivityKind.ADDED: AccountActivityKind.INVENTORY_ADDED,
        InventoryActivityKind.EDITED: AccountActivityKind.INVENTORY_EDITED,
        InventoryActivityKind.CLOSED: AccountActivityKind.INVENTORY_CLOSED,
    }

    return tuple(
        AccountActivity(
            occurred_at=activity.occurred_at,
            kind=kind_map[activity.kind],
            target=activity.batch,
        )
        for activity in list_inventory_activity_for_actor(
            actor=user,
            limit=ACCOUNT_ACTIVITY_LIMIT,
        )
    )


def _customer_activities(user) -> tuple[AccountActivity, ...]:
    kind_map = {
        CustomerActivityKind.CREATED: AccountActivityKind.CUSTOMER_CREATED,
        CustomerActivityKind.EDITED: AccountActivityKind.CUSTOMER_EDITED,
        CustomerActivityKind.ACTIVATED: AccountActivityKind.CUSTOMER_ACTIVATED,
        CustomerActivityKind.DEACTIVATED: (
            AccountActivityKind.CUSTOMER_DEACTIVATED
        ),
    }

    return tuple(
        AccountActivity(
            occurred_at=activity.occurred_at,
            kind=kind_map[activity.kind],
            target=activity.customer,
        )
        for activity in list_customer_activity_for_actor(
            actor=user,
            limit=ACCOUNT_ACTIVITY_LIMIT,
        )
    )
