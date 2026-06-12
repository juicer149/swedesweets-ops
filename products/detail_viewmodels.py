from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.urls import reverse

from accounts.roles import Capability, RoleSpec
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_secondary_get_action,
)
from common.ui import UiCard
from inventory.mini_cards import build_batch_mini_card
from inventory.models import InventoryBatch
from inventory.selectors import AvailableStockRow
from products.models import Product
from products.presentation import (
    ProductTagPresentation,
    product_attribute_tags,
    product_detail_card_class,
    product_detail_status_class,
    product_status_icon,
)
from products.selectors import ProductDeliveredDemandSummary


@dataclass(frozen=True, slots=True)
class ProductStockSummary:
    product: Product
    batch_count: int
    physical_quantity: int
    reserved_quantity: int
    available_quantity: int

    @property
    def physical_quantity_label(self) -> str:
        return self.product.stock_quantity_label(self.physical_quantity)

    @property
    def reserved_quantity_label(self) -> str:
        return self.product.stock_quantity_label(self.reserved_quantity)

    @property
    def available_quantity_label(self) -> str:
        return self.product.stock_quantity_label(self.available_quantity)

    @classmethod
    def empty(cls, *, product: Product) -> ProductStockSummary:
        return cls(
            product=product,
            batch_count=0,
            physical_quantity=0,
            reserved_quantity=0,
            available_quantity=0,
        )

    @classmethod
    def from_available_stock_row(
        cls,
        *,
        product: Product,
        row: AvailableStockRow | None,
    ) -> ProductStockSummary:
        if row is None:
            return cls.empty(product=product)

        return cls(
            product=product,
            batch_count=row.batch_count,
            physical_quantity=row.physical_quantity,
            reserved_quantity=row.reserved_quantity,
            available_quantity=row.available_quantity,
        )


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class ProductBatchRow:
    batch_id: str
    batch_href: str
    quantity: int
    quantity_label: str
    best_before: object
    location: str
    status: str
    card: UiCard


@dataclass(frozen=True, slots=True)
class ProductDemandSummary:
    product: Product
    delivered_order_count: int
    delivered_quantity: int
    average_quantity_per_delivered_order: Decimal
    last_delivered_at: datetime | None

    @property
    def delivered_quantity_label(self) -> str:
        return self.product.stock_quantity_label(self.delivered_quantity)

    @property
    def average_quantity_per_delivered_order_label(self) -> str:
        value = self.average_quantity_per_delivered_order.normalize()

        if value == value.to_integral_value():
            display_value = str(int(value))
        else:
            display_value = format(value, "f").rstrip("0").rstrip(".")

        unit = (
            self.product.stock_unit_singular
            if self.average_quantity_per_delivered_order == 1
            else self.product.stock_unit_plural
        )

        return f"{display_value} {unit}"

    @classmethod
    def from_delivered_demand_summary(
        cls,
        *,
        product: Product,
        summary: ProductDeliveredDemandSummary,
    ) -> ProductDemandSummary:
        return cls(
            product=product,
            delivered_order_count=summary.delivered_order_count,
            delivered_quantity=summary.delivered_quantity,
            average_quantity_per_delivered_order=(
                summary.average_quantity_per_delivered_order
            ),
            last_delivered_at=summary.last_delivered_at,
        )


@dataclass(frozen=True, slots=True)
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
    role_spec: RoleSpec,
    cancel_url: str,
) -> ProductDetailContext:
    stock = ProductStockSummary.from_available_stock_row(
        product=product,
        row=stock_row,
    )
    demand = ProductDemandSummary.from_delivered_demand_summary(
        product=product,
        summary=demand_summary,
    )

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
            secondary_actions=build_product_secondary_actions(
                product=product,
                role_spec=role_spec,
            ),
        ),
        title=product.display_name,
        description="",
        cancel_url=cancel_url,
    )


def build_product_secondary_actions(
    *,
    product: Product,
    role_spec: RoleSpec,
) -> tuple[DetailAction, ...]:
    if not can_edit_product(product=product, role_spec=role_spec):
        return ()

    return (
        build_edit_product_action(
            href=reverse("products:edit", kwargs={"product_pk": product.pk}),
        ),
    )


def can_edit_product(
    *,
    product: Product,
    role_spec: RoleSpec,
) -> bool:
    return role_spec.allows(Capability.EDIT_PRODUCTS)


def build_edit_product_action(*, href: str) -> DetailAction:
    return build_secondary_get_action(
        label="Edit product",
        href=href,
    )


def _build_product_header(product: Product) -> DetailHeader:
    return DetailHeader(
        eyebrow=product.code_label,
        title=product.display_name,
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
            summary=product.display_name,
            body_template="products/includes/detail_panel_product.html",
            icon="lollipop",
            is_active=True,
        ),
        DetailPanel(
            key="inventory",
            label="Inventory",
            summary=product.stock_quantity_label(stock.available_quantity),
            body_template="products/includes/detail_panel_inventory.html",
            icon="inventory",
        ),
        DetailPanel(
            key="demand",
            label="Demand",
            summary=product.stock_quantity_label(demand.delivered_quantity),
            body_template="products/includes/detail_panel_demand.html",
            icon="truck",
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
                quantity=batch.quantity,
                quantity_label=batch.product.stock_quantity_label(batch.quantity),
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
