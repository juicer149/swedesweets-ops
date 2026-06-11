from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.ui import (
    StatusPresentation,
    UiCard,
    UiCardRow,
    UiText,
)
from accounts.roles import Capability, RoleSpec
from common.page_header import PageHeader, PageHeaderAction
from common.table_controls import QuickJumpOption, QuickJumpSearch
from products.models import Product
from products.presentation import (
    ProductTagPresentation,
    product_attribute_tags,
    product_code_label,
    product_manufacturer_label,
    product_status_presentation,
)


@dataclass(frozen=True, slots=True)
class ProductPageRow:
    product: Product
    status: StatusPresentation
    detail_href: str
    weight_label: str
    unit_label: str
    card: UiCard


def build_products_page_header(*, role_spec: RoleSpec) -> PageHeader:
    return PageHeader(
        title="Products",
        title_id="products-title",
        action=_build_add_product_header_action(role_spec=role_spec),
    )


def _build_add_product_header_action(
    *,
    role_spec: RoleSpec,
) -> PageHeaderAction | None:
    if not role_spec.allows(Capability.CREATE_PRODUCTS):
        return None

    return PageHeaderAction(
        label="Add product",
        href=reverse("products:create"),
        aria_label="Add a new product",
    )


def build_product_page_rows(products: list[Product]) -> list[ProductPageRow]:
    return [
        _build_product_page_row(product)
        for product in products
    ]


def _build_product_page_row(product: Product) -> ProductPageRow:
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


def build_product_quick_jump_search(
    rows: list[ProductPageRow],
) -> QuickJumpSearch:
    return QuickJumpSearch(
        title="Find",
        title_id="products-quick-jump-title",
        select_id="products-quick-jump",
        placeholder="Search by code, brand, or name",
        aria_label="Find product",
        options=[
            QuickJumpOption(
                label=row.product.catalog_label,
                url=row.detail_href,
            )
            for row in rows
        ],
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
        href=detail_href,
        aria_label=f"View product {product.display_name}",
        footer_hint="Open details →",
        rows=_product_card_rows(
            product=product,
            status=status,
        ),
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
            css_class="ui-card-id",
        ),
        right=status.text,
    )


def _product_brand_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.brand,
            css_class="ui-card-title",
        ),
    )


def _product_name_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.name,
            css_class="ui-card-title",
        ),
    )


def _product_manufacturer_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product_manufacturer_label(product),
            css_class="ui-card-meta",
        ),
    )


def _product_weight_row(product: Product) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=product.unit_weight_label,
            css_class="ui-card-strong",
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


def _product_detail_href(product: Product) -> str:
    return reverse("products:detail", kwargs={"product_pk": product.pk})
