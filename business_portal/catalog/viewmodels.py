from __future__ import annotations

from collections.abc import Iterable

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from business.selectors import BusinessCatalogEntry
from common.catalog.viewmodels import ProductCardVM
from common.ui import UiText
from products.localization import translated_product_name


def build_business_product_cards(
    *,
    entries: Iterable[BusinessCatalogEntry],
    language_code: str,
) -> tuple[ProductCardVM, ...]:
    return tuple(
        _build_business_product_card(
            entry=entry,
            language_code=language_code,
        )
        for entry in entries
    )


def _build_business_product_card(
    *,
    entry: BusinessCatalogEntry,
    language_code: str,
) -> ProductCardVM:
    product = entry.product

    product_name = translated_product_name(
        product,
        language_code=language_code,
    )

    return ProductCardVM(
        product_id=product.id,
        name=product_name,
        package_label=product.unit_weight_label,
        badge_label=_("Available"),

        primary_action=UiText(
            text=_("Add to order"),
            href=reverse(
                "business_portal:catalog_add_product",
                kwargs={
                    "product_id": product.id,
                },
            ),
            css_class="product-card__button",
            aria_label=_("Add %(product)s to order")
            % {
                "product": product_name,
            },
        ),
    )
