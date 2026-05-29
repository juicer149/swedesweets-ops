from __future__ import annotations

from dataclasses import dataclass

from common.ui import (
    StatusPresentation,
    TONE_MUTED,
    TONE_SUCCESS,
    UiText,
)
from products.models import Product

# TODO: Remove one-use mobile card CSS constants after product cards have
# stabilized. Product list card classes now live directly in list_viewmodels.py.

PRODUCT_CARD_CLASS = "mobile-card mobile-card--product"

PRODUCT_CODE_CLASS = "ui-card-id"
PRODUCT_BRAND_CLASS = "ui-card-muted"
PRODUCT_TITLE_CLASS = "ui-card-title"
PRODUCT_WEIGHT_CLASS = "ui-card-strong"
PRODUCT_ACTION_CLASS = "text-link"

PRODUCT_ACTION_LABEL = "View product →"

PRODUCT_DETAIL_PANEL_ICON = "lollipop"
PRODUCT_INVENTORY_PANEL_ICON = "inventory"
PRODUCT_DEMAND_PANEL_ICON = "truck"

PRODUCT_EDIT_LABEL = "Edit product"

PRODUCT_TAG_ICON_CLASS = "product-tag__icon"
PRODUCT_TAG_VEGAN_CLASS = "product-tag product-tag--vegan"


@dataclass(frozen=True)
class ProductTagPresentation:
    label: str
    css_class: str
    icon: str
    icon_class: str


PRODUCT_STATUS_ACTIVE = StatusPresentation(
    value="active",
    label="Active",
    tone=TONE_SUCCESS,
    text=UiText(
        text="Active",
        css_class="status-text status-text--success",
    ),
)

PRODUCT_STATUS_INACTIVE = StatusPresentation(
    value="inactive",
    label="Inactive",
    tone=TONE_MUTED,
    text=UiText(
        text="Inactive",
        css_class="status-text status-text--muted",
    ),
)

PRODUCT_TAG_VEGAN = ProductTagPresentation(
    label="Vegan",
    css_class=PRODUCT_TAG_VEGAN_CLASS,
    icon="leaf",
    icon_class=PRODUCT_TAG_ICON_CLASS,
)


def product_status_presentation(product: Product) -> StatusPresentation:
    if product.active:
        return PRODUCT_STATUS_ACTIVE

    return PRODUCT_STATUS_INACTIVE


def product_detail_status_class(product: Product) -> str:
    return product_status_presentation(product).text.css_class


def product_status_icon(product: Product) -> str:
    if product.active:
        return "lollipop"

    return "x"


def product_detail_card_class(product: Product) -> str:
    if product.active:
        return ""

    return "content-card--muted"


def product_code_label(product: Product) -> str:
    if product.internal_number is None:
        return product.sku

    return f"#{product.internal_number}"


def product_manufacturer_label(product: Product) -> str:
    if product.manufacturer:
        return product.manufacturer

    return "—"


def product_brand_label(product: Product) -> str:
    if product.brand:
        return product.brand

    return "—"


def product_weight_label(product: Product) -> str:
    return product.unit_weight_label


def product_vegan_label(product: Product) -> str:
    return "Yes" if product.vegan else "No"


def product_attribute_tags(product: Product) -> tuple[ProductTagPresentation, ...]:
    tags: list[ProductTagPresentation] = []

    if product.vegan:
        tags.append(PRODUCT_TAG_VEGAN)

    return tuple(tags)


def stock_quantity_label(*, product: Product, quantity: int) -> str:
    return product.stock_quantity_label(quantity)
