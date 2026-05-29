from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.table_controls import QuickJumpOption, QuickJumpSearch
from common.ui import (
    QuantityInfo,
    StatusPresentation,
    UiCard,
    UiCardRow,
    UiText,
    build_quantity_info,
)
from inventory.low_stock import LOW_STOCK_THRESHOLD
from inventory.models import InventoryBatch
from inventory.presentation import (
    INVENTORY_ACTION_CLASS,
    INVENTORY_BATCH_ACTION_LABEL,
    INVENTORY_BATCH_TITLE_CLASS,
    INVENTORY_CARD_CLASS,
    INVENTORY_LOCATION_CLASS,
    INVENTORY_LOCATION_LABEL,
    INVENTORY_QUANTITY_CLASS,
    INVENTORY_VIEW_BATCHES_LABEL,
    INVENTORY_VIEW_PRODUCTS_LABEL,
    batch_quantity_label,
    batch_status_presentation,
    expiry_css_class,
    product_available_quantity_label,
    product_batch_count_label,
    product_physical_quantity_label,
    product_reserved_quantity_label,
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
    quantity_label: str
    detail_href: str
    card: UiCard


@dataclass(frozen=True)
class ProductStockPageRow:
    product_id: int
    product_href: str
    code_label: str
    product_label: str
    catalog_label: str
    product_name: str
    brand: str
    stock_unit_label: str
    batch_count: int
    physical_quantity: int
    physical_quantity_label: str
    reserved_quantity: int
    reserved_quantity_label: str
    available_quantity: int
    available_quantity_label: str
    available_quantity_info: QuantityInfo
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
    quantity = build_quantity_info(
        quantity=row.batch.quantity,
        low_threshold=LOW_STOCK_THRESHOLD,
    )
    quantity_text = batch_quantity_label(row.batch)
    detail_href = _batch_detail_href(row.batch)

    return BatchPageRow(
        batch=row.batch,
        expiry=row.expiry,
        status=status,
        quantity=quantity,
        quantity_label=quantity_text,
        detail_href=detail_href,
        card=_batch_card(
            row=row,
            status=status,
            detail_href=detail_href,
            quantity=quantity,
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
    product_href = reverse("products:detail", kwargs={"product_pk": row.product_id})
    available_quantity_info = build_quantity_info(
        quantity=row.available_quantity,
        low_threshold=LOW_STOCK_THRESHOLD,
    )

    return ProductStockPageRow(
        product_id=row.product_id,
        product_href=product_href,
        code_label=row.code_label,
        product_label=_product_stock_product_label(row),
        catalog_label=row.catalog_label,
        product_name=row.product_name,
        brand=row.brand,
        stock_unit_label=row.product.stock_unit_singular,
        batch_count=row.batch_count,
        physical_quantity=row.physical_quantity,
        physical_quantity_label=product_physical_quantity_label(row),
        reserved_quantity=row.reserved_quantity,
        reserved_quantity_label=product_reserved_quantity_label(row),
        available_quantity=row.available_quantity,
        available_quantity_label=product_available_quantity_label(row),
        available_quantity_info=available_quantity_info,
        status=status,
        card=_product_stock_card(
            row=row,
            status=status,
            product_href=product_href,
            available_quantity_info=available_quantity_info,
        ),
    )


def build_batch_quick_jump_search(
    rows: list[BatchPageRow],
) -> QuickJumpSearch:
    return QuickJumpSearch(
        title="Find batch",
        title_id="inventory-batch-search-title",
        select_id="inventory-batch-search",
        placeholder="Search batch, product or location",
        aria_label="Search inventory batches",
        options=[
            QuickJumpOption(
                label=_batch_quick_jump_label(row),
                url=row.detail_href,
            )
            for row in rows
        ],
    )


def build_product_stock_quick_jump_search(
    rows: list[ProductStockPageRow],
) -> QuickJumpSearch:
    return QuickJumpSearch(
        title="Find product stock",
        title_id="inventory-product-stock-search-title",
        select_id="inventory-product-stock-search",
        placeholder="Search product stock",
        aria_label="Search product stock",
        options=[
            QuickJumpOption(
                label=_product_stock_quick_jump_label(row),
                url=row.product_href,
            )
            for row in rows
        ],
    )


def _batch_quick_jump_label(row: BatchPageRow) -> str:
    return (
        f"{row.batch.batch_id} · "
        f"{row.batch.product.code_label} · "
        f"{row.batch.product.display_name}"
    )


def _product_stock_quick_jump_label(row: ProductStockPageRow) -> str:
    return f"{row.code_label} · {row.product_name}"


def _product_stock_product_label(row: AvailableStockRow) -> str:
    return (
        f"{row.code_label} · "
        f"{row.product.display_name} · "
        f"{row.product.weight_label}"
    )


def _batch_card(
    *,
    row: BatchListRow,
    status: StatusPresentation,
    detail_href: str,
    quantity: QuantityInfo,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class=INVENTORY_CARD_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=row.batch.batch_id,
                    css_class="inventory-card__id",
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=row.batch.product.brand,
                    css_class="inventory-card__brand",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.batch.product.name,
                    css_class="inventory-card__name",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.batch.product.weight_label,
                    css_class="inventory-card__weight",
                ),
                right=UiText(
                    text=batch_quantity_label(row.batch),
                    css_class=(
                        "inventory-card__value "
                        f"{quantity.css_class}"
                    ),
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.batch.location,
                    css_class="inventory-card__value",
                    label=INVENTORY_LOCATION_LABEL,
                    label_class="inventory-card__label",
                ),
                right=UiText(
                    text=row.batch.best_before.strftime("%d-%m-%y"),
                    css_class="inventory-card__value",
                    label=row.expiry.label,
                    label_class=(
                        "inventory-card__label "
                        f"{expiry_css_class(row)}"
                    ),
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
    product_href: str,
    available_quantity_info: QuantityInfo,
) -> UiCard:
    physical_quantity_label = row.product.stock_quantity_label(
        row.physical_quantity
    )
    reserved_quantity_label = row.product.stock_quantity_label(
        row.reserved_quantity
    )
    available_quantity_label = row.product.stock_quantity_label(
        row.available_quantity
    )

    return UiCard(
        tone=status.tone,
        css_class=INVENTORY_CARD_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=row.product.code_label,
                    css_class="inventory-card__id",
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=row.product.brand,
                    css_class="inventory-card__brand",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.product.name,
                    css_class="inventory-card__name",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.product.weight_label,
                    css_class="inventory-card__weight",
                ),
                right=UiText(
                    text=product_batch_count_label(row),
                    css_class="inventory-card__value",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text="In stock",
                    css_class="inventory-card__metric-label",
                ),
                center=UiText(
                    text="Reserved",
                    css_class="inventory-card__metric-label",
                ),
                right=UiText(
                    text="Available",
                    css_class="inventory-card__metric-label",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=physical_quantity_label,
                    css_class="inventory-card__metric-value",
                ),
                center=UiText(
                    text=reserved_quantity_label,
                    css_class="inventory-card__metric-value inventory-card__metric-value--reserved",
                ),
                right=UiText(
                    text=available_quantity_label,
                    css_class=(
                        "inventory-card__metric-value "
                        "inventory-card__metric-value--available "
                        f"{available_quantity_info.css_class}"
                    ),
                ),
            ),
        ),
        action=UiText(
            text="View product →",
            href=product_href,
            css_class=INVENTORY_ACTION_CLASS,
        ),
    )


def _batch_detail_href(batch: InventoryBatch) -> str:
    return reverse("inventory:detail", kwargs={"batch_pk": batch.pk})
