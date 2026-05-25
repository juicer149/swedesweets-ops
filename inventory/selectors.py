"""
Inventory read selectors.

Selectors are read-only query functions. They should not change model state,
create objects, or perform business workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Case, Count, IntegerField, QuerySet, Sum, Value, When
from django.utils import timezone

from common.table_tools import normalize_sort
from inventory.models import InventoryBatch
from orders.models import Allocation, Order
from products.models import Product


DEFAULT_BATCH_SORT = "best_before"

BATCH_SORTS: dict[str, tuple[str, ...]] = {
    "batch": ("batch_id",),
    "-batch": ("-batch_id",),
    "product": ("product__name", "batch_id"),
    "-product": ("-product__name", "batch_id"),
    "best_before": ("best_before", "batch_id"),
    "-best_before": ("-best_before", "batch_id"),
    "boxes": ("boxes", "batch_id"),
    "-boxes": ("-boxes", "batch_id"),
    "status": ("status_rank", "best_before", "batch_id"),
    "-status": ("-status_rank", "best_before", "batch_id"),
    "location": ("location", "batch_id"),
    "-location": ("-location", "batch_id"),
}

EXPIRY_CRITICAL_DAYS = 14
EXPIRY_SOON_DAYS = 60


@dataclass(frozen=True)
class ExpiryInfo:
    state: str
    label: str
    days_left: int


@dataclass(frozen=True)
class BatchListRow:
    batch: InventoryBatch
    expiry: ExpiryInfo


@dataclass(frozen=True)
class PhysicalStockRow:
    product_id: int
    sku: str
    product_name: str
    brand: str
    boxes: int
    batch_count: int


@dataclass(frozen=True)
class AvailableStockRow:
    product_id: int
    sku: str
    product_name: str
    brand: str
    batch_count: int
    physical_boxes: int
    reserved_boxes: int
    available_boxes: int


@dataclass(frozen=True)
class _PhysicalStockByProductIdRow:
    sku: str
    product_name: str
    brand: str
    physical_boxes: int
    batch_count: int


def list_batch_rows(
    *,
    status: str | None = None,
    sort: str | None = None,
    today: date | None = None,
) -> list[BatchListRow]:
    today = today or timezone.localdate()

    return _build_batch_rows(
        batches=list_batches(status=status, sort=sort),
        today=today,
    )


def list_batches(
    *,
    status: str | None = None,
    sort: str | None = None,
) -> QuerySet[InventoryBatch]:
    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=BATCH_SORTS,
        default_sort=DEFAULT_BATCH_SORT,
    )

    batches = (
        InventoryBatch.objects
        .select_related("product")
        .annotate(status_rank=_batch_status_rank_expression())
    )

    if status in InventoryBatch.Status.values:
        batches = batches.filter(status=status)

    return batches.order_by(*BATCH_SORTS[normalized_sort])


def physical_boxes_by_product() -> list[PhysicalStockRow]:
    rows = (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .values(
            "product_id",
            "product__sku",
            "product__name",
            "product__brand",
        )
        .annotate(
            total_boxes=Sum("boxes"),
            batch_count=Count("id"),
        )
        .order_by("product__brand", "product__name", "product__sku")
    )

    return [
        PhysicalStockRow(
            product_id=row["product_id"],
            sku=row["product__sku"],
            product_name=row["product__name"],
            brand=row["product__brand"],
            boxes=row["total_boxes"] or 0,
            batch_count=row["batch_count"] or 0,
        )
        for row in rows
    ]


def available_boxes_by_product() -> list[AvailableStockRow]:
    physical_rows = _physical_boxes_by_product_id()
    reserved_boxes_by_product_id = _reserved_boxes_by_product_id()

    rows: list[AvailableStockRow] = []

    for product_id, physical_row in physical_rows.items():
        reserved_boxes = reserved_boxes_by_product_id.get(product_id, 0)
        available_boxes = physical_row.physical_boxes - reserved_boxes

        rows.append(
            AvailableStockRow(
                product_id=product_id,
                sku=physical_row.sku,
                product_name=physical_row.product_name,
                brand=physical_row.brand,
                batch_count=physical_row.batch_count,
                physical_boxes=physical_row.physical_boxes,
                reserved_boxes=reserved_boxes,
                available_boxes=max(available_boxes, 0),
            )
        )

    return sorted(
        rows,
        key=lambda row: (row.brand, row.product_name, row.sku),
    )


def available_boxes_by_product_id() -> dict[int, int]:
    return {
        row.product_id: row.available_boxes
        for row in available_boxes_by_product()
    }


def list_available_batches_for_product(
    *,
    product: Product,
) -> QuerySet[InventoryBatch]:
    return (
        InventoryBatch.objects
        .filter(
            product=product,
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .select_related("product")
        .order_by("best_before", "batch_id")
    )


def list_available_batches() -> QuerySet[InventoryBatch]:
    return (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .select_related("product")
        .order_by("product__sku", "best_before", "batch_id")
    )


def list_depleted_batches() -> QuerySet[InventoryBatch]:
    return (
        InventoryBatch.objects
        .filter(status=InventoryBatch.Status.DEPLETED)
        .select_related("product")
        .order_by("product__sku", "batch_id")
    )


def list_expiring_batch_rows_for_dashboard(
    *,
    limit: int = 3,
    today: date | None = None,
) -> list[BatchListRow]:
    today = today or timezone.localdate()

    batches = (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .select_related("product")
        .order_by("best_before", "batch_id")[:limit]
    )

    return _build_batch_rows(
        batches=batches,
        today=today,
    )


def count_expiring_batches() -> int:
    return (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .count()
    )


def list_low_stock_products_for_dashboard(
    *,
    threshold: int = 10,
    limit: int = 3,
) -> list[AvailableStockRow]:
    rows = [
        row
        for row in available_boxes_by_product()
        if row.available_boxes <= threshold
    ]

    return sorted(
        rows,
        key=lambda row: (row.available_boxes, row.brand, row.product_name),
    )[:limit]


def count_low_stock_products(
    *,
    threshold: int = 10,
) -> int:
    return sum(
        1
        for row in available_boxes_by_product()
        if row.available_boxes <= threshold
    )


def build_expiry_info(
    *,
    best_before: date,
    today: date,
) -> ExpiryInfo:
    days_left = (best_before - today).days

    if days_left < 0:
        return ExpiryInfo(
            state="expired",
            label="Expired",
            days_left=days_left,
        )

    if days_left == 0:
        return ExpiryInfo(
            state="critical",
            label="Expires today",
            days_left=days_left,
        )

    if days_left <= EXPIRY_CRITICAL_DAYS:
        return ExpiryInfo(
            state="critical",
            label=f"Expires in {days_left} days",
            days_left=days_left,
        )

    if days_left <= EXPIRY_SOON_DAYS:
        return ExpiryInfo(
            state="soon",
            label=f"Expires in {days_left} days",
            days_left=days_left,
        )

    return ExpiryInfo(
        state="safe",
        label="Best before",
        days_left=days_left,
    )


def list_batch_allocations(*, batch: InventoryBatch) -> list[Allocation]:
    """Return allocation usage for one inventory batch.

    This is not full audit history. It shows how the batch has been used by
    orders through reservation, consumption and cancellation records.
    """

    return list(
        Allocation.objects
        .filter(batch=batch)
        .select_related(
            "order",
            "order__customer",
            "order_line",
            "order_line__product",
        )
        .order_by("-order__created_at", "-id")
    )

def _build_batch_rows(
    *,
    batches: QuerySet[InventoryBatch],
    today: date,
) -> list[BatchListRow]:
    return [
        BatchListRow(
            batch=batch,
            expiry=build_expiry_info(
                best_before=batch.best_before,
                today=today,
            ),
        )
        for batch in batches
    ]


def _batch_status_rank_expression() -> Case:
    return Case(
        When(status=InventoryBatch.Status.ACTIVE, then=Value(1)),
        When(status=InventoryBatch.Status.DEPLETED, then=Value(2)),
        When(status=InventoryBatch.Status.CLOSED, then=Value(3)),
        default=Value(99),
        output_field=IntegerField(),
    )


def _physical_boxes_by_product_id() -> dict[int, _PhysicalStockByProductIdRow]:
    rows = (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .values(
            "product_id",
            "product__sku",
            "product__name",
            "product__brand",
        )
        .annotate(
            total_boxes=Sum("boxes"),
            batch_count=Count("id"),
        )
    )

    return {
        row["product_id"]: _PhysicalStockByProductIdRow(
            sku=row["product__sku"],
            product_name=row["product__name"],
            brand=row["product__brand"],
            physical_boxes=row["total_boxes"] or 0,
            batch_count=row["batch_count"] or 0,
        )
        for row in rows
    }


def _reserved_boxes_by_product_id() -> dict[int, int]:
    rows = (
        Allocation.objects
        .filter(
            status=Allocation.Status.RESERVED,
            order__status=Order.Status.PLACED,
        )
        .values("batch__product_id")
        .annotate(total_reserved=Sum("boxes"))
    )

    return {
        row["batch__product_id"]: row["total_reserved"] or 0
        for row in rows
    }
