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
    PRODUCT_ACTION_CLASS,
    PRODUCT_ACTION_LABEL,
    PRODUCT_BRAND_CLASS,
    PRODUCT_CARD_CLASS,
    PRODUCT_CODE_CLASS,
    PRODUCT_TITLE_CLASS,
    PRODUCT_WEIGHT_CLASS,
    ProductTagPresentation,
    product_attribute_tags,
    product_brand_label,
    product_code_label,
    product_manufacturer_label,
    product_status_presentation,
    product_weight_label,
)


@dataclass(frozen=True)
class ProductPageRow:
    product: Product
    status: StatusPresentation
    detail_href: str
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
        css_class=PRODUCT_CARD_CLASS,
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
        _product_title_row(product),
        _product_brand_row(product),
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
            css_class=PRODUCT_CODE_CLASS,
        ),
        right=status.text,
    )


def _product_title_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.name,
            css_class=PRODUCT_TITLE_CLASS,
        ),
    )


def _product_brand_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=(
                f"{product_brand_label(product)}"
                f" · {product_manufacturer_label(product)}"
            ),
            css_class=PRODUCT_BRAND_CLASS,
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


def _product_weight_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product_weight_label(product),
            css_class=PRODUCT_WEIGHT_CLASS,
        ),
    )


def _product_detail_action(detail_href: str) -> UiText:
    return UiText(
        text=PRODUCT_ACTION_LABEL,
        href=detail_href,
        css_class=PRODUCT_ACTION_CLASS,
    )


def _product_detail_href(product: Product) -> str:
    return reverse("products:detail", kwargs={"product_pk": product.pk})
