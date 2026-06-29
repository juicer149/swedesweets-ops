from __future__ import annotations

from dataclasses import dataclass

from common.ui import (
    TONE_MUTED,
    TONE_SUCCESS,
    StatusPresentation,
    UiText,
)
from products.models import Product


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
    css_class="product-tag product-tag--vegan",
    icon="leaf",
    icon_class="product-tag__icon",
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


def product_manufacturer_label(product: Product) -> str:
    if product.manufacturer:
        return product.manufacturer

    return "—"


def product_brand_label(product: Product) -> str:
    if product.brand:
        return product.brand

    return "—"


def product_vegan_label(product: Product) -> str:
    return "Yes" if product.vegan else "No"


def product_attribute_tags(product: Product) -> tuple[ProductTagPresentation, ...]:
    tags: list[ProductTagPresentation] = []

    if product.vegan:
        tags.append(PRODUCT_TAG_VEGAN)

    return tuple(tags)


def translated_product_name(
    product: Product,
    *,
    language_code: str,
) -> str:
    translations = getattr(product, "prefetched_translations", None)

    if translations is not None:
        for translation in translations:
            if translation.language_code == language_code and translation.name:
                return translation.name

        return product.display_name

    translation = product.translations.filter(language_code=language_code).first()

    if translation is None:
        return product.display_name

    return translation.name


def translated_product_catalog_label(
    product: Product,
    *,
    language_code: str,
) -> str:
    return (
        f"{product.code_label} · "
        f"{translated_product_name(product, language_code=language_code)} · "
        f"{product.unit_weight_label}"
    )
