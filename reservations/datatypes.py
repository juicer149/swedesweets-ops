from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orders.models import Order


@dataclass(frozen=True, slots=True)
class ReservationPick:
    sku: str
    product_name: str
    batch_code: str
    location: str
    quantity: int
    quantity_label: str


@dataclass(frozen=True, slots=True)
class BatchUsage:
    order: Order
    buyer_name: str
    customer_id: int | None
    quantity: int
    quantity_label: str
    allocation_status: str
    order_status: str
    is_active_reservation: bool
