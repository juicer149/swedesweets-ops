from __future__ import annotations

from common.ui import UiCard, UiCardRow, UiText
from products.models import Product
from products.presentation import product_status_presentation


def build_product_mini_card(
    *,
    product: Product,
    product_href: str,
) -> UiCard:
    """Build a compact product relation card.

    Use this when the surrounding page already gives the context, for example
    batch detail where the question is: which product does this batch belong to?
    """

    status = product_status_presentation(product)

    return UiCard(
        tone=status.tone,
        css_class="mobile-card mobile-card--relation mobile-card--product-mini",
        href=product_href,
        aria_label=f"View product {product.display_name}",
        footer_hint="Open product →",
        rows=(
            UiCardRow(
                left=UiText(
                    text=product.code_label,
                    css_class="ui-card-id",
                ),
                right=UiText(
                    text=product.weight_label,
                    css_class="ui-card-meta",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=product.display_name,
                    css_class="ui-card-title",
                ),
            ),
        ),
    )


def build_product_quantity_mini_card(
    *,
    product: Product,
    product_href: str,
    quantity_label: str,
) -> UiCard:
    """Build a compact product card with an operational quantity.

    Use this for order contents, allocations, or any list where the important
    information is: how much of this product is involved?
    """

    status = product_status_presentation(product)

    return UiCard(
        tone=status.tone,
        css_class="mobile-card mobile-card--relation mobile-card--product-mini",
        href=product_href,
        aria_label=f"View product {product.display_name}",
        footer_hint="Open product →",
        rows=(
            UiCardRow(
                left=UiText(
                    text=quantity_label,
                    css_class="ui-card-id",
                ),
                right=UiText(
                    text=product.weight_label,
                    css_class="ui-card-meta",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=f"{product.code_label} • {product.display_name}",
                    css_class="ui-card-title",
                ),
            ),
        ),
    )
