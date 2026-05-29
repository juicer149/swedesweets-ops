from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.ui import (
    StatusPresentation,
    UiCard,
    UiCardRow,
    UiText,
)
from products.models import Product
from products.presentation import (
    PRODUCT_ACTION_LABEL,
    ProductTagPresentation,
    product_attribute_tags,
    product_code_label,
    product_manufacturer_label,
    product_status_presentation,
)


@dataclass(frozen=True)
class ProductPageRow:
    product: Product
    status: StatusPresentation
    detail_href: str
    weight_label: str
    unit_label: str
    card: UiCard


def build_product_page_rows(products: list[Product]) -> list[ProductPageRow]:
    return [
        build_product_page_row(product)
        for product in products
    ]


def build_product_page_row(product: Product) -> ProductPageRow:
    status = product_status_presentation(product)
    detail_href = _product_detail_href(product)

    return ProductPageRow(
        product=product,
        status=status,
        detail_href=detail_href,
        weight_label=product.weight_label,
        unit_label=product.stock_unit_singular,
        card=_product_card(
            product=product,
            status=status,
            detail_href=detail_href,
        ),
    )


def _product_card(
    *,
    product: Product,
    status: StatusPresentation,
    detail_href: str,
) -> UiCard:
    return UiCard(
        tone=status.tone,
        css_class="mobile-card mobile-card--product",
        rows=_product_card_rows(
            product=product,
            status=status,
        ),
        action=_product_detail_action(detail_href),
    )


def _product_card_rows(
    *,
    product: Product,
    status: StatusPresentation,
) -> tuple[UiCardRow, ...]:
    rows: list[UiCardRow] = [
        _product_header_row(product, status),
        _product_brand_row(product),
        _product_name_row(product),
        _product_manufacturer_row(product),
        _product_weight_row(product),
    ]

    for tag in product_attribute_tags(product):
        rows.append(_product_tag_row(tag))

    return tuple(rows)


def _product_header_row(
    product: Product,
    status: StatusPresentation,
) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product_code_label(product),
            css_class="product-card__id",
        ),
        right=status.text,
    )


def _product_brand_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.brand,
            css_class="product-card__brand",
        ),
    )


def _product_name_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.name,
            css_class="product-card__name",
        ),
    )


def _product_manufacturer_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product_manufacturer_label(product),
            css_class="product-card__manufacturer",
        ),
    )


def _product_weight_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.unit_weight_label,
            css_class="product-card__weight",
        ),
    )


def _product_tag_row(tag: ProductTagPresentation) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=tag.label,
            css_class=tag.css_class,
            icon=tag.icon,
            icon_class=tag.icon_class,
        ),
    )


def _product_detail_action(detail_href: str) -> UiText:
    return UiText(
        text=PRODUCT_ACTION_LABEL,
        href=detail_href,
        css_class="text-link",
    )


def _product_detail_href(product: Product) -> str:
    return reverse("products:detail", kwargs={"product_pk": product.pk})
