from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_secondary_get_action,
    build_danger_get_action,
)
from common.ui import UiCard
from inventory.models import InventoryBatch
from inventory.presentation import (
    batch_detail_card_class,
    batch_detail_status_class,
    batch_status_icon,
)
from inventory.selectors import build_expiry_info
from orders.mini_cards import build_order_usage_mini_card
from orders.models import Allocation
from products.mini_cards import build_product_mini_card


@dataclass(frozen=True)
class BatchStockSummary:
    physical_quantity: int
    physical_quantity_label: str
    reserved_quantity: int
    reserved_quantity_label: str
    available_quantity: int
    available_quantity_label: str
    is_orderable: bool

    @classmethod
    def from_batch_and_allocations(
        cls,
        *,
        batch: InventoryBatch,
        allocations: list[Allocation],
    ) -> BatchStockSummary:
        reserved_quantity = sum(
            allocation.quantity
            for allocation in allocations
            if allocation.status == Allocation.Status.RESERVED
        )
        available_quantity = max(batch.quantity - reserved_quantity, 0)

        return cls(
            physical_quantity=batch.quantity,
            physical_quantity_label=batch.product.stock_quantity_label(batch.quantity),
            reserved_quantity=reserved_quantity,
            reserved_quantity_label=batch.product.stock_quantity_label(
                reserved_quantity
            ),
            available_quantity=available_quantity,
            available_quantity_label=batch.product.stock_quantity_label(
                available_quantity
            ),
            is_orderable=(
                batch.status == InventoryBatch.Status.ACTIVE
                and batch.product.active
                and available_quantity > 0
            ),
        )


@dataclass(frozen=True)
class BatchUsageRow:
    order_id: int
    order_href: str
    customer_name: str
    customer_href: str
    quantity: int
    quantity_label: str
    allocation_status: str
    order_status: str
    card: UiCard


@dataclass(frozen=True)
class BatchDetailContext:
    batch: InventoryBatch
    stock: BatchStockSummary
    product_href: str
    product_card: UiCard
    usage_rows: list[BatchUsageRow]
    usage_count: int
    detail_card: DetailCard
    title: str
    description: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "batch": self.batch,
            "stock": self.stock,
            "product_href": self.product_href,
            "product_card": self.product_card,
            "usage_rows": self.usage_rows,
            "usage_count": self.usage_count,
            "detail_card": self.detail_card,
            "title": self.title,
            "description": self.description,
            "cancel_url": self.cancel_url,
        }


def build_batch_detail_context(
    *,
    batch: InventoryBatch,
    allocations: list[Allocation],
    cancel_url: str,
    edit_url: str = "",
    close_url: str = "",
) -> BatchDetailContext:
    usage_rows = _build_usage_rows(allocations)
    stock = BatchStockSummary.from_batch_and_allocations(
        batch=batch,
        allocations=allocations,
    )
    product_href = reverse(
        "products:detail",
        kwargs={"product_pk": batch.product_id},
    )

    return BatchDetailContext(
        batch=batch,
        stock=stock,
        product_href=product_href,
        product_card=build_product_mini_card(
            product=batch.product,
            product_href=product_href,
        ),
        usage_rows=usage_rows,
        usage_count=len(usage_rows),
        detail_card=DetailCard(
            header=_build_batch_header(batch),
            panels=_build_batch_detail_panels(
                batch=batch,
                stock=stock,
                usage_count=len(usage_rows),
            ),
            content_card_class=batch_detail_card_class(batch),
            secondary_actions=_build_secondary_actions(
                batch=batch,
                edit_url=edit_url,
                close_url=close_url,
            ),
        ),
        title=f"Batch {batch.batch_id}",
        description="",
        cancel_url=cancel_url,
    )


def build_edit_batch_action(*, href: str) -> DetailAction:
    return build_secondary_get_action(
        label="Edit batch",
        href=href,
    )


def build_close_batch_action(*, href: str) -> DetailAction:
    return build_danger_get_action( 
        label="Close batch",
        href=href,
    )


def _build_secondary_actions(
    *,
    batch: InventoryBatch,
    edit_url: str,
    close_url: str,
) -> tuple[DetailAction, ...]:
    actions: list[DetailAction] = []

    if batch.status != InventoryBatch.Status.CLOSED:
        if edit_url:
            actions.append(build_edit_batch_action(href=edit_url))

        if close_url:
            actions.append(build_close_batch_action(href=close_url))

    return tuple(actions)


def _build_batch_header(batch: InventoryBatch) -> DetailHeader:
    return DetailHeader(
        eyebrow="Batch",
        title=batch.batch_id,
        status_label=batch.get_status_display(),
        status_class=batch_detail_status_class(batch),
        status_icon=batch_status_icon(batch),
    )


def _build_batch_detail_panels(
    *,
    batch: InventoryBatch,
    stock: BatchStockSummary,
    usage_count: int,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="batch",
            label="Batch",
            summary=stock.available_quantity_label,
            body_template="inventory/includes/detail_panel_batch.html",
            icon="tag",
            is_active=True,
        ),
        DetailPanel(
            key="usage",
            label="Usage",
            summary=_usage_summary(usage_count),
            body_template="inventory/includes/detail_panel_usage.html",
            icon="inventory",
        ),
    )


def _build_usage_rows(allocations: list[Allocation]) -> list[BatchUsageRow]:
    rows: list[BatchUsageRow] = []

    for allocation in allocations:
        order_href = reverse(
            "orders:detail",
            kwargs={"order_id": allocation.order_id},
        )
        customer_name = allocation.order.customer.name
        allocation_status = allocation.get_status_display()
        quantity = allocation.quantity
        quantity_text = allocation.batch.product.stock_quantity_label(quantity)

        rows.append(
            BatchUsageRow(
                order_id=allocation.order_id,
                order_href=order_href,
                customer_name=customer_name,
                customer_href=reverse(
                    "customers:detail",
                    kwargs={"customer_pk": allocation.order.customer_id},
                ),
                quantity=quantity,
                quantity_label=quantity_text,
                allocation_status=allocation_status,
                order_status=allocation.order.get_status_display(),
                card=build_order_usage_mini_card(
                    order=allocation.order,
                    order_href=order_href,
                    customer_name=customer_name,
                    allocation_status=allocation_status,
                    quantity_label_text=quantity_text,
                ),
            )
        )

    return rows


def _usage_summary(usage_count: int) -> str:
    if usage_count == 1:
        return "1 allocation"

    return f"{usage_count} allocations"


def batch_expiry_label(batch: InventoryBatch) -> str:
    expiry = build_expiry_info(
        best_before=batch.best_before,
        today=timezone.localdate(),
    )

    return expiry.label
