from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.ui import (
    QuantityInfo,
    StatusPresentation,
    UiCard,
    UiCardRow,
    UiText,
    build_quantity_info,
)
from inventory.models import InventoryBatch
from inventory.presentation import (
    INVENTORY_ACTION_CLASS,
    INVENTORY_BATCH_ACTION_LABEL,
    INVENTORY_BATCH_TITLE_CLASS,
    INVENTORY_BOXES_CLASS,
    INVENTORY_CARD_CLASS,
    INVENTORY_LOCATION_CLASS,
    INVENTORY_LOCATION_LABEL,
    INVENTORY_META_CLASS,
    INVENTORY_PRODUCT_SKU_CLASS,
    INVENTORY_VIEW_BATCHES_LABEL,
    INVENTORY_VIEW_PRODUCTS_LABEL,
    batch_boxes_label,
    batch_status_presentation,
    expiry_css_class,
    product_available_boxes_label,
    product_batch_count_label,
    product_physical_boxes_label,
    product_reserved_boxes_label,
    product_stock_status_presentation,
)
from inventory.selectors import (
    AvailableStockRow,
    BatchListRow,
    ExpiryInfo,
)


@dataclass(frozen=True)
class InventoryViewLink:
    key: str
    label: str
    href: str
    is_active: bool


@dataclass(frozen=True)
class BatchPageRow:
    batch: InventoryBatch
    expiry: ExpiryInfo
    status: StatusPresentation
    quantity: QuantityInfo
    detail_href: str
    card: UiCard


@dataclass(frozen=True)
class ProductStockPageRow:
    product_id: int
    code_label: str
    catalog_label: str
    product_name: str
    brand: str
    batch_count: int
    physical_boxes: int
    reserved_boxes: int
    available_boxes: int
    status: StatusPresentation
    card: UiCard


def build_inventory_view_links(
    *,
    active_view: str,
    batches_href: str,
    products_href: str,
) -> tuple[InventoryViewLink, ...]:
    return (
        InventoryViewLink(
            key="batches",
            label=INVENTORY_VIEW_BATCHES_LABEL,
            href=batches_href,
            is_active=active_view == "batches",
        ),
        InventoryViewLink(
            key="products",
            label=INVENTORY_VIEW_PRODUCTS_LABEL,
            href=products_href,
            is_active=active_view == "products",
        ),
    )


def build_batch_page_rows(rows: list[BatchListRow]) -> list[BatchPageRow]:
    return [
        build_batch_page_row(row)
        for row in rows
    ]


def build_batch_page_row(row: BatchListRow) -> BatchPageRow:
    status = batch_status_presentation(row.batch)
    quantity = build_quantity_info(boxes=row.batch.boxes)
    detail_href = _batch_detail_href(row.batch)

    return BatchPageRow(
        batch=row.batch,
        expiry=row.expiry,
        status=status,
        quantity=quantity,
        detail_href=detail_href,
        card=_batch_card(
            row=row,
            status=status,
            detail_href=detail_href,
        ),
    )


def build_product_stock_page_rows(
    rows: list[AvailableStockRow],
) -> list[ProductStockPageRow]:
    return [
        build_product_stock_page_row(row)
        for row in rows
    ]


def build_product_stock_page_row(row: AvailableStockRow) -> ProductStockPageRow:
    status = product_stock_status_presentation(row)

    return ProductStockPageRow(
        product_id=row.product_id,
        code_label=row.code_label,
        catalog_label=row.catalog_label,
        product_name=row.product_name,
        brand=row.brand,
        batch_count=row.batch_count,
        physical_boxes=row.physical_boxes,
        reserved_boxes=row.reserved_boxes,
        available_boxes=row.available_boxes,
        status=status,
        card=_product_stock_card(row=row, status=status),
    )


def _batch_card(
    *,
    row: BatchListRow,
    status: StatusPresentation,
    detail_href: str,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class=INVENTORY_CARD_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=row.batch.batch_id,
                    css_class=INVENTORY_BATCH_TITLE_CLASS,
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=row.batch.product.display_name,
                    css_class=INVENTORY_PRODUCT_SKU_CLASS,
                ),
                right=UiText(
                    text=batch_boxes_label(row.batch),
                    css_class=INVENTORY_BOXES_CLASS,
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.batch.location,
                    css_class=INVENTORY_LOCATION_CLASS,
                    label=INVENTORY_LOCATION_LABEL,
                ),
                right=UiText(
                    text=row.expiry.label,
                    css_class=expiry_css_class(row),
                    subtext=row.batch.best_before.strftime("%d-%m-%y"),
                    subtext_class="expiry-text__date",
                ),
            ),
        ),
        action=_batch_detail_action(detail_href),
    )


def _batch_detail_action(detail_href: str) -> UiText:
    return UiText(
        text=INVENTORY_BATCH_ACTION_LABEL,
        href=detail_href,
        css_class=INVENTORY_ACTION_CLASS,
    )


def _product_stock_card(
    *,
    row: AvailableStockRow,
    status: StatusPresentation,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class=INVENTORY_CARD_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=row.catalog_label,
                    css_class=INVENTORY_BATCH_TITLE_CLASS,
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=product_batch_count_label(row),
                    css_class=INVENTORY_META_CLASS,
                ),
                right=UiText(
                    text=product_physical_boxes_label(row),
                    css_class=INVENTORY_META_CLASS,
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=product_reserved_boxes_label(row),
                    css_class=INVENTORY_META_CLASS,
                ),
                right=UiText(
                    text=product_available_boxes_label(row),
                    css_class=INVENTORY_BOXES_CLASS,
                ),
            ),
        ),
    )


def _batch_detail_href(batch: InventoryBatch) -> str:
    return reverse("inventory:detail", kwargs={"batch_pk": batch.pk})
