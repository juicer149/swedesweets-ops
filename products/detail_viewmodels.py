from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.urls import reverse

from common.detail_cards import (
    ACTION_METHOD_GET,
    ACTION_TONE_SECONDARY,
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
)
from common.ui import UiCard
from inventory.mini_cards import build_batch_mini_card

from inventory.models import InventoryBatch
from inventory.selectors import AvailableStockRow
from products.models import Product
from products.presentation import (
    PRODUCT_BACK_TO_PRODUCTS_LABEL,
    PRODUCT_DEMAND_PANEL_ICON,
    PRODUCT_DETAIL_PANEL_ICON,
    PRODUCT_EDIT_LABEL,
    PRODUCT_INVENTORY_PANEL_ICON,
    ProductTagPresentation,
    boxes_label,
    product_attribute_tags,
    product_detail_card_class,
    product_detail_status_class,
    product_status_icon,
)
from products.selectors import ProductDeliveredDemandSummary


@dataclass(frozen=True)
class ProductStockSummary:
    batch_count: int
    physical_boxes: int
    reserved_boxes: int
    available_boxes: int

    @classmethod
    def empty(cls) -> ProductStockSummary:
        return cls(
            batch_count=0,
            physical_boxes=0,
            reserved_boxes=0,
            available_boxes=0,
        )

    @classmethod
    def from_available_stock_row(
        cls,
        row: AvailableStockRow | None,
    ) -> ProductStockSummary:
        if row is None:
            return cls.empty()

        return cls(
            batch_count=row.batch_count,
            physical_boxes=row.physical_boxes,
            reserved_boxes=row.reserved_boxes,
            available_boxes=row.available_boxes,
        )


@dataclass(frozen=True)
class ProductProfileSummary:
    description: str
    ingredients: str
    image_url: str

    @classmethod
    def from_product(cls, product: Product) -> ProductProfileSummary:
        try:
            profile = product.profile
        except Product.profile.RelatedObjectDoesNotExist:
            return cls.empty()

        return cls(
            description=profile.description,
            ingredients=profile.ingredients,
            image_url=profile.image_url,
        )

    @classmethod
    def empty(cls) -> ProductProfileSummary:
        return cls(
            description="",
            ingredients="",
            image_url="",
        )


@dataclass(frozen=True)
class ProductBatchRow:
    batch_id: str
    batch_href: str
    boxes: int
    best_before: object
    location: str
    status: str
    card: UiCard


@dataclass(frozen=True)
class ProductDemandSummary:
    delivered_order_count: int
    delivered_boxes: int
    average_boxes_per_delivered_order: Decimal
    last_delivered_at: datetime | None

    @classmethod
    def from_delivered_demand_summary(
        cls,
        summary: ProductDeliveredDemandSummary,
    ) -> ProductDemandSummary:
        return cls(
            delivered_order_count=summary.delivered_order_count,
            delivered_boxes=summary.delivered_boxes,
            average_boxes_per_delivered_order=(
                summary.average_boxes_per_delivered_order
            ),
            last_delivered_at=summary.last_delivered_at,
        )


@dataclass(frozen=True)
class ProductDetailContext:
    product: Product
    profile: ProductProfileSummary
    attribute_tags: tuple[ProductTagPresentation, ...]
    stock: ProductStockSummary
    batch_rows: list[ProductBatchRow]
    demand: ProductDemandSummary
    detail_card: DetailCard
    title: str
    description: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "profile": self.profile,
            "attribute_tags": self.attribute_tags,
            "stock": self.stock,
            "batch_rows": self.batch_rows,
            "demand": self.demand,
            "detail_card": self.detail_card,
            "title": self.title,
            "description": self.description,
            "cancel_url": self.cancel_url,
        }


def build_product_detail_context(
    *,
    product: Product,
    stock_row: AvailableStockRow | None,
    active_batches: list[InventoryBatch],
    demand_summary: ProductDeliveredDemandSummary,
    edit_url: str,
    cancel_url: str,
) -> ProductDetailContext:
    stock = ProductStockSummary.from_available_stock_row(stock_row)
    demand = ProductDemandSummary.from_delivered_demand_summary(demand_summary)

    return ProductDetailContext(
        product=product,
        profile=ProductProfileSummary.from_product(product),
        attribute_tags=product_attribute_tags(product),
        stock=stock,
        batch_rows=_build_batch_rows(active_batches),
        demand=demand,
        detail_card=DetailCard(
            header=_build_product_header(product),
            panels=_build_product_detail_panels(
                product=product,
                stock=stock,
                demand=demand,
            ),
            content_card_class=product_detail_card_class(product),
            secondary_actions=(
                build_edit_product_action(href=edit_url),
                build_back_to_products_action(href=cancel_url),
            ),
        ),
        title=product.name,
        description="",
        cancel_url=cancel_url,
    )


def build_edit_product_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=PRODUCT_EDIT_LABEL,
        href=href,
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_SECONDARY,
    )


def build_back_to_products_action(*, href: str) -> DetailAction:
    return DetailAction(
        label=PRODUCT_BACK_TO_PRODUCTS_LABEL,
        href=href,
        method=ACTION_METHOD_GET,
        tone=ACTION_TONE_SECONDARY,
    )


def _build_product_header(product: Product) -> DetailHeader:
    return DetailHeader(
        eyebrow="Product",
        title=product.name,
        status_label=_product_status_label(product),
        status_class=product_detail_status_class(product),
        status_icon=product_status_icon(product),
    )


def _build_product_detail_panels(
    *,
    product: Product,
    stock: ProductStockSummary,
    demand: ProductDemandSummary,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="product",
            label="Product",
            summary=product.sku,
            body_template="products/includes/detail_panel_product.html",
            icon=PRODUCT_DETAIL_PANEL_ICON,
            is_active=True,
        ),
        DetailPanel(
            key="inventory",
            label="Inventory",
            summary=boxes_label(stock.available_boxes),
            body_template="products/includes/detail_panel_inventory.html",
            icon=PRODUCT_INVENTORY_PANEL_ICON,
        ),
        DetailPanel(
            key="demand",
            label="Demand",
            summary=boxes_label(demand.delivered_boxes),
            body_template="products/includes/detail_panel_demand.html",
            icon=PRODUCT_DEMAND_PANEL_ICON,
        ),
    )


def _build_batch_rows(
    batches: list[InventoryBatch],
) -> list[ProductBatchRow]:
    rows: list[ProductBatchRow] = []

    for batch in batches:
        batch_href = reverse("inventory:detail", kwargs={"batch_pk": batch.pk})

        rows.append(
            ProductBatchRow(
                batch_id=batch.batch_id,
                batch_href=batch_href,
                boxes=batch.boxes,
                best_before=batch.best_before,
                location=batch.location,
                status=batch.get_status_display(),
                card=build_batch_mini_card(
                    batch=batch,
                    batch_href=batch_href,
                ),
            )
        )

    return rows

def _product_status_label(product: Product) -> str:
    return "Active" if product.active else "Inactive"
