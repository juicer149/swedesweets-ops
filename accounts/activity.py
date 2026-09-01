from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AccountActivityKind(StrEnum):
    ORDER_PLACED = "order_placed"
    ORDER_PACKED = "order_packed"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_EDITED = "order_edited"

    PRODUCT_CREATED = "product_created"
    PRODUCT_EDITED = "product_edited"
    PRODUCT_ACTIVATED = "product_activated"
    PRODUCT_DEACTIVATED = "product_deactivated"

    INVENTORY_ADDED = "inventory_added"
    INVENTORY_EDITED = "inventory_edited"
    INVENTORY_CLOSED = "inventory_closed"

    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_EDITED = "customer_edited"
    CUSTOMER_ACTIVATED = "customer_activated"
    CUSTOMER_DEACTIVATED = "customer_deactivated"


@dataclass(frozen=True, slots=True)
class AccountActivity:
    occurred_at: datetime
    kind: AccountActivityKind
    target: object
