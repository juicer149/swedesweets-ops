"""
Inventory read selectors.

Selectors are read-only query functions. They should not change model state,
create objects, or perform business workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, TypeAlias

from django.db.models import Case, Count, IntegerField, QuerySet, Sum, Value, When
from django.utils import timezone

from common.table_tools import normalize_sort
from inventory.expiry import (
    EXPIRY_SOON_DAYS, 
    ExpiryInfo, 
    build_expiry_info,
    orderable_best_before_cutoff,
)

from inventory.low_stock import LOW_STOCK_THRESHOLD, is_low_stock
from inventory.models import InventoryBatch
from orders.models import Allocation, Order
from products.models import Product


DEFAULT_BATCH_SORT = "status"

BATCH_SORTS: dict[str, tuple[str, ...]] = {
    "batch": ("batch_id",),
    "-batch": ("-batch_id",),
    "product": (
        "product__internal_number",
        "product__brand",
        "product__name",
        "batch_id",
    ),
    "-product": (
        "-product__internal_number",
        "-product__brand",
        "-product__name",
        "batch_id",
    ),
    "best_before": ("best_before", "batch_id"),
    "-best_before": ("-best_before", "-batch_id"),
    "quantity": ("quantity", "batch_id"),
    "-quantity": ("-quantity", "-batch_id"),
    "status": ("status_rank", "best_before", "batch_id"),
    "-status": ("-status_rank", "-best_before", "-batch_id"),
    "location": ("location", "batch_id"),
    "-location": ("-location", "-batch_id"),
}

DEFAULT_PRODUCT_STOCK_SORT = "product"

PRODUCT_STOCK_SORTS: dict[str, tuple[str, ...]] = {
    "product": ("internal_number_sort", "brand", "product_name"),
    "-product": ("-internal_number_sort", "-brand", "-product_name"),
    "batches": ("batch_count", "internal_number_sort", "product_name"),
    "unit": ("stock_unit_sort", "internal_number_sort", "product_name"),
    "-unit": ("-stock_unit_sort", "internal_number_sort", "product_name"),
    "-batches": ("-batch_count", "internal_number_sort", "product_name"),
    "physical": ("physical_quantity", "internal_number_sort", "product_name"),
    "-physical": ("-physical_quantity", "internal_number_sort", "product_name"),
    "reserved": ("reserved_quantity", "internal_number_sort", "product_name"),
    "-reserved": ("-reserved_quantity", "internal_number_sort", "product_name"),
    "available": ("available_quantity", "internal_number_sort", "product_name"),
    "-available": ("-available_quantity", "internal_number_sort", "product_name"),
}


@dataclass(frozen=True)
class BatchListRow:
    batch: InventoryBatch
    expiry: ExpiryInfo


@dataclass(frozen=True)
class PhysicalStockRow:
    product: Product
    quantity: int
    batch_count: int

    @property
    def product_id(self) -> int:
        return self.product.id

    @property
    def sku(self) -> str:
        return self.product.sku

    @property
    def internal_number_sort(self) -> int:
        return self.product.internal_number or 999_999

    @property
    def code_label(self) -> str:
        return self.product.code_label

    @property
    def catalog_label(self) -> str:
        return self.product.catalog_label

    @property
    def product_name(self) -> str:
        return self.product.display_name

    @property
    def brand(self) -> str:
        return self.product.brand


@dataclass(frozen=True)
class AvailableStockRow:
    product: Product
    batch_count: int
    physical_quantity: int
    reserved_quantity: int
    available_quantity: int

    @property
    def product_id(self) -> int:
        return self.product.id

    @property
    def sku(self) -> str:
        return self.product.sku

    @property
    def internal_number_sort(self) -> int:
        return self.product.internal_number or 999_999

    @property
    def code_label(self) -> str:
        return self.product.code_label

    @property
    def catalog_label(self) -> str:
        return self.product.catalog_label

    @property
    def product_name(self) -> str:
        return self.product.display_name

    @property
    def brand(self) -> str:
        return self.product.brand

    @property
    def stock_unit_sort(self) -> int:
        return self.product.stock_unit


@dataclass(frozen=True)
class _PhysicalStockTotals:
    physical_quantity: int
    batch_count: int


ProductStockSortKey: TypeAlias = Callable[[AvailableStockRow], tuple[object, ...]]


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


def physical_quantity_by_product() -> list[PhysicalStockRow]:
    stock_totals_by_product_id = _physical_stock_totals_by_product_id()
    products_by_id = _products_by_id(stock_totals_by_product_id.keys())

    rows = [
        PhysicalStockRow(
            product=product,
            quantity=stock_totals_by_product_id[product_id].physical_quantity,
            batch_count=stock_totals_by_product_id[product_id].batch_count,
        )
        for product_id, product in products_by_id.items()
    ]

    return sorted(rows, key=lambda row: row.product.catalog_sort_key)


def available_quantity_by_product() -> list[AvailableStockRow]:
    stock_totals_by_product_id = _physical_stock_totals_by_product_id()
    reserved_quantity_by_product_id = _reserved_quantity_by_product_id()
    products_by_id = _products_by_id(stock_totals_by_product_id.keys())

    rows: list[AvailableStockRow] = []

    for product_id, product in products_by_id.items():
        stock_totals = stock_totals_by_product_id[product_id]
        reserved_quantity = reserved_quantity_by_product_id.get(product_id, 0)
        available_quantity = stock_totals.physical_quantity - reserved_quantity

        rows.append(
            AvailableStockRow(
                product=product,
                batch_count=stock_totals.batch_count,
                physical_quantity=stock_totals.physical_quantity,
                reserved_quantity=reserved_quantity,
                available_quantity=max(available_quantity, 0),
            )
        )

    return sorted(rows, key=lambda row: row.product.catalog_sort_key)


def available_quantity_by_product_id() -> dict[int, int]:
    return {
        row.product_id: row.available_quantity
        for row in available_quantity_by_product()
    }


def sort_available_stock_rows(
    *,
    rows: list[AvailableStockRow],
    sort: str | None,
) -> list[AvailableStockRow]:
    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=PRODUCT_STOCK_SORTS,
        default_sort=DEFAULT_PRODUCT_STOCK_SORT,
    )

    reverse_sort = normalized_sort.startswith("-")
    sort_key = normalized_sort.lstrip("-")
    key_function = _product_stock_sort_key_functions()[sort_key]

    return sorted(
        rows,
        key=key_function,
        reverse=reverse_sort,
    )


def list_available_batches_for_product(
    *,
    product: Product,
) -> QuerySet[InventoryBatch]:
    return (
        InventoryBatch.objects
        .filter(
            product=product,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
        )
        .select_related("product")
        .order_by("best_before", "batch_id")
    )


def list_available_batches() -> QuerySet[InventoryBatch]:
    return (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
        )
        .select_related("product")
        .order_by(
            "product__internal_number",
            "product__brand",
            "product__name",
            "best_before",
            "batch_id",
        )
    )


def list_depleted_batches() -> QuerySet[InventoryBatch]:
    return (
        InventoryBatch.objects
        .filter(status=InventoryBatch.Status.DEPLETED)
        .select_related("product")
        .order_by(
            "product__internal_number",
            "product__brand",
            "product__name",
            "batch_id",
        )
    )


def list_expiring_batch_rows_for_dashboard(
    *,
    limit: int = 3,
    days: int = EXPIRY_SOON_DAYS,
    today: date | None = None,
) -> list[BatchListRow]:
    return list_expiring_batch_rows(
        days=days,
        today=today,
    )[:limit]


def list_expiring_batch_rows(
    *,
    days: int = EXPIRY_SOON_DAYS,
    today: date | None = None,
) -> list[BatchListRow]:
    today = today or timezone.localdate()
    cutoff_date = today + timedelta(days=days)

    batches = (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gte=today,
            best_before__lte=cutoff_date,
        )
        .select_related("product")
        .order_by("best_before", "batch_id")
    )

    return _build_batch_rows(
        batches=batches,
        today=today,
    )


def count_expiring_batches(
    *,
    days: int = EXPIRY_SOON_DAYS,
    today: date | None = None,
) -> int:
    today = today or timezone.localdate()
    cutoff_date = today + timedelta(days=days)

    return (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gte=today,
            best_before__lte=cutoff_date,
        )
        .count()
    )


def list_low_stock_products(
    *,
    threshold: int = LOW_STOCK_THRESHOLD,
) -> list[AvailableStockRow]:
    rows = [
        row
        for row in available_quantity_by_product()
        if is_low_stock(
            available_quantity=row.available_quantity,
            threshold=threshold,
        )
    ]

    return sorted(
        rows,
        key=lambda row: (
            row.available_quantity,
            row.product.catalog_sort_key,
        ),
    )


def list_low_stock_products_for_dashboard(
    *,
    threshold: int = LOW_STOCK_THRESHOLD,
    limit: int = 3,
) -> list[AvailableStockRow]:
    return list_low_stock_products(threshold=threshold)[:limit]


def count_low_stock_products(
    *,
    threshold: int = LOW_STOCK_THRESHOLD,
) -> int:
    return len(list_low_stock_products(threshold=threshold))


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


def orderable_quantity_by_product_id(
    *,
    today: date | None = None,
) -> dict[int, int]:
    today = today or timezone.localdate()
    cutoff_date = orderable_best_before_cutoff(today=today)

    physical_quantity_by_product_id = _orderable_physical_quantity_by_product_id(
        cutoff_date=cutoff_date,
    )
    reserved_quantity_by_product_id = _orderable_reserved_quantity_by_product_id(
        cutoff_date=cutoff_date,
    )

    return {
        product_id: max(
            physical_quantity - reserved_quantity_by_product_id.get(product_id, 0),
            0,
        )
        for product_id, physical_quantity in physical_quantity_by_product_id.items()
    }


def _orderable_physical_quantity_by_product_id(
    *,
    cutoff_date: date,
) -> dict[int, int]:
    rows = (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gt=cutoff_date,
        )
        .values("product_id")
        .annotate(total_quantity=Sum("quantity"))
    )

    return {
        row["product_id"]: row["total_quantity"] or 0
        for row in rows
    }


def _orderable_reserved_quantity_by_product_id(
    *,
    cutoff_date: date,
) -> dict[int, int]:
    rows = (
        Allocation.objects
        .filter(
            status=Allocation.Status.RESERVED,
            order__status=Order.Status.PLACED,
            batch__status=InventoryBatch.Status.ACTIVE,
            batch__quantity__gt=0,
            batch__best_before__gt=cutoff_date,
        )
        .values("batch__product_id")
        .annotate(total_reserved=Sum("quantity"))
    )

    return {
        row["batch__product_id"]: row["total_reserved"] or 0
        for row in rows
    }

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


def _physical_stock_totals_by_product_id() -> dict[int, _PhysicalStockTotals]:
    rows = (
        InventoryBatch.objects
        .filter(
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
        )
        .values("product_id")
        .annotate(
            total_quantity=Sum("quantity"),
            batch_count=Count("id"),
        )
    )

    return {
        row["product_id"]: _PhysicalStockTotals(
            physical_quantity=row["total_quantity"] or 0,
            batch_count=row["batch_count"] or 0,
        )
        for row in rows
    }


def _products_by_id(product_ids) -> dict[int, Product]:
    products = Product.objects.filter(id__in=product_ids)

    return {
        product.id: product
        for product in products
    }


def _reserved_quantity_by_product_id() -> dict[int, int]:
    rows = (
        Allocation.objects
        .filter(
            status=Allocation.Status.RESERVED,
            order__status=Order.Status.PLACED,
        )
        .values("batch__product_id")
        .annotate(total_reserved=Sum("quantity"))
    )

    return {
        row["batch__product_id"]: row["total_reserved"] or 0
        for row in rows
    }


def _product_stock_sort_key_functions() -> dict[str, ProductStockSortKey]:
    return {
        "product": lambda row: (
            row.internal_number_sort,
            row.brand.casefold(),
            row.product_name.casefold(),
        ),
        "batches": lambda row: (
            row.batch_count,
            row.internal_number_sort,
            row.product_name.casefold(),
        ),
        "unit": lambda row: (
            row.stock_unit_sort,
            row.internal_number_sort,
            row.product_name.casefold(),
        ),
        "physical": lambda row: (
            row.physical_quantity,
            row.internal_number_sort,
            row.product_name.casefold(),
        ),
        "reserved": lambda row: (
            row.reserved_quantity,
            row.internal_number_sort,
            row.product_name.casefold(),
        ),
        "available": lambda row: (
            row.available_quantity,
            row.internal_number_sort,
            row.product_name.casefold(),
        ),
    }
