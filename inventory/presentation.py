from __future__ import annotations

from common.ui import (
    StatusPresentation,
    TONE_DANGER,
    TONE_MUTED,
    TONE_SUCCESS,
    TONE_WARNING,
    UiText,
)
from inventory.models import InventoryBatch
from inventory.selectors import AvailableStockRow, BatchListRow

INVENTORY_CARD_CLASS = "mobile-card mobile-card--inventory"

INVENTORY_VIEW_BATCHES_LABEL = "Batches"
INVENTORY_VIEW_PRODUCTS_LABEL = "Product stock"


INVENTORY_STATUS_ACTIVE = StatusPresentation(
    value=InventoryBatch.Status.ACTIVE,
    label="Active",
    tone=TONE_SUCCESS,
    text=UiText(
        text="Active",
        css_class="status-text status-text--success",
    ),
)

INVENTORY_STATUS_DEPLETED = StatusPresentation(
    value=InventoryBatch.Status.DEPLETED,
    label="Depleted",
    tone=TONE_WARNING,
    text=UiText(
        text="Depleted",
        css_class="status-text status-text--warning",
    ),
)

INVENTORY_STATUS_CLOSED = StatusPresentation(
    value=InventoryBatch.Status.CLOSED,
    label="Closed",
    tone=TONE_MUTED,
    text=UiText(
        text="Closed",
        css_class="status-text status-text--muted",
    ),
)

PRODUCT_STOCK_STATUS_AVAILABLE = StatusPresentation(
    value="available",
    label="Available",
    tone=TONE_SUCCESS,
    text=UiText(
        text="Available",
        css_class="status-text status-text--success",
    ),
)

PRODUCT_STOCK_STATUS_RESERVED = StatusPresentation(
    value="reserved",
    label="Reserved",
    tone=TONE_WARNING,
    text=UiText(
        text="Reserved",
        css_class="status-text status-text--warning",
    ),
)

PRODUCT_STOCK_STATUS_OUT = StatusPresentation(
    value="out",
    label="Out",
    tone=TONE_DANGER,
    text=UiText(
        text="Out",
        css_class="status-text status-text--danger",
    ),
)


def batch_status_presentation(batch: InventoryBatch) -> StatusPresentation:
    if batch.status == InventoryBatch.Status.ACTIVE:
        return INVENTORY_STATUS_ACTIVE

    if batch.status == InventoryBatch.Status.DEPLETED:
        return INVENTORY_STATUS_DEPLETED

    return INVENTORY_STATUS_CLOSED


def product_stock_status_presentation(
    row: AvailableStockRow,
) -> StatusPresentation:
    if row.available_quantity > 0:
        return PRODUCT_STOCK_STATUS_AVAILABLE

    if row.reserved_quantity > 0:
        return PRODUCT_STOCK_STATUS_RESERVED

    return PRODUCT_STOCK_STATUS_OUT


def batch_detail_status_class(batch: InventoryBatch) -> str:
    return batch_status_presentation(batch).text.css_class


def batch_status_icon(batch: InventoryBatch) -> str:
    if batch.status == InventoryBatch.Status.ACTIVE:
        return "box"

    if batch.status == InventoryBatch.Status.DEPLETED:
        return "packed"

    return "x"


def batch_detail_card_class(batch: InventoryBatch) -> str:
    if batch.status == InventoryBatch.Status.ACTIVE:
        return "content-card--deliver"

    if batch.status == InventoryBatch.Status.DEPLETED:
        return "content-card--pack"

    if batch.status == InventoryBatch.Status.CLOSED:
        return "content-card--muted"

    return ""


def batch_quantity_label(batch: InventoryBatch) -> str:
    return f"{batch.product.stock_quantity_label(batch.quantity)}"


def quantity_label(*, product, quantity: int) -> str:
    return product.stock_quantity_label(quantity)


def product_batch_count_label(row: AvailableStockRow) -> str:
    return f"{row.batch_count} {_batch_word(row.batch_count)}"


def product_physical_quantity_label(row: AvailableStockRow) -> str:
    return f"{row.product.stock_quantity_label(row.physical_quantity)}"


def product_reserved_quantity_label(row: AvailableStockRow) -> str:
    return f"{row.product.stock_quantity_label(row.reserved_quantity)}"


def product_available_quantity_label(row: AvailableStockRow) -> str:
    return f"{row.product.stock_quantity_label(row.available_quantity)}"


def expiry_css_class(row: BatchListRow) -> str:
    if row.batch.status == InventoryBatch.Status.CLOSED:
        return "expiry-text expiry-text--muted"

    return f"expiry-text expiry-text--{row.expiry.state}"


def _batch_word(count: int) -> str:
    return "batch" if count == 1 else "batches"
