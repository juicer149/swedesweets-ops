from __future__ import annotations

from collections.abc import Iterable

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from common.catalog.viewmodels import (
    CatalogOfferVM,
    ProductCardVM,
)
from common.ui import UiText
from pricing.models import CommercialPrice
from products.localization import translated_product_name
from products.models import ProductProfile


def build_business_product_cards(
    *,
    products: Iterable[CatalogProduct],
    language_code: str,
) -> tuple[ProductCardVM, ...]:
    return tuple(
        _build_business_product_card(
            catalog_product=catalog_product,
            language_code=language_code,
        )
        for catalog_product in products
    )


def _build_business_product_card(
    *,
    catalog_product: CatalogProduct,
    language_code: str,
) -> ProductCardVM:
    product = catalog_product.product

    product_name = translated_product_name(
        product,
        language_code=language_code,
    )

    category_key = _catalog_category_key(
        product
    )

    return ProductCardVM(
        product_id=product.id,
        name=product_name,
        package_label=product.unit_weight_label,
        badge_label=None,
        primary_action=UiText(
            text=_("Add to order"),
            href=reverse(
                "business_portal:catalog_add_product",
                kwargs={
                    "product_id": product.id,
                },
            ),
            css_class=(
                "button button--sm button--soft "
                "button--tone-positive"
            ),
            aria_label=_("Add %(product)s to order")
            % {
                "product": product_name,
            },
        ),
        image_url=_product_image_url(
            product
        ),
        secondary_action=UiText(
            text=_("Details"),
            href=reverse(
                "business_portal:catalog_product",
                kwargs={
                    "product_id": product.id,
                },
            ),
            css_class="text-link",
            aria_label=_("View details for %(product)s")
            % {
                "product": product_name,
            },
        ),
        offers=tuple(
            build_business_offer_viewmodel(
                offer
            )
            for offer in catalog_product.offers
        ),
        category_key=category_key,
        search_text=_catalog_search_text(
            product_name=product_name,
            package_label=product.unit_weight_label,
            category_key=category_key,
        ),
    )


def build_business_catalog_payload(
    *,
    product_cards: Iterable[ProductCardVM],
) -> list[dict[str, object]]:
    return [
        card.catalog_payload()
        for card in product_cards
    ]


def build_business_offer_viewmodel(
    offer: CatalogOffer,
) -> CatalogOfferVM:
    if offer.kind == CatalogOfferKind.STANDARD:
        return CatalogOfferVM(
            commercial_price_id=offer.commercial_price_id,
            batch_id=None,
            kind=offer.kind.value,
            label=str(
                _("Standard")
            ),
            badge_label=None,
            price_label=_price_label(
                offer
            ),
            availability_label=_availability_label(
                offer.available_units
            ),
            available_units=offer.available_units,
        )

    reason_label = _reason_label(
        offer.reason
    )

    return CatalogOfferVM(
        commercial_price_id=offer.commercial_price_id,
        batch_id=offer.batch_id,
        kind=offer.kind.value,
        label=reason_label,
        badge_label=reason_label,
        price_label=_price_label(
            offer
        ),
        availability_label=_availability_label(
            offer.available_units
        ),
        available_units=offer.available_units,
    )


def _catalog_category_key(
    product,
) -> str:
    try:
        category = product.profile.category
    except ProductProfile.DoesNotExist:
        return "other"

    if category == ProductProfile.Category.CANDY:
        return "candy"

    if category == ProductProfile.Category.CHIPS:
        return "chips"

    if category == ProductProfile.Category.DIP_MIX:
        return "dip_mix"

    return "other"


def _catalog_search_text(
    *,
    product_name: str,
    package_label: str,
    category_key: str,
) -> str:
    return " ".join(
        (
            product_name,
            package_label,
            category_key.replace(
                "_",
                " ",
            ),
        )
    ).casefold()


def _product_image_url(
    product,
) -> str | None:
    try:
        image_url = product.profile.image_url
    except ProductProfile.DoesNotExist:
        return None

    return image_url or None


def _reason_label(
    reason: str | None,
) -> str:
    if not reason:
        return str(
            _("Special offer")
        )

    try:
        return str(
            CommercialPrice.Reason(
                reason
            ).label
        )
    except ValueError:
        return str(
            _("Special offer")
        )


def _price_label(
    offer: CatalogOffer,
) -> str | None:
    if offer.price is None:
        return None

    return f"€{offer.price:.2f}"


def _availability_label(
    available_units: int,
) -> str:
    if available_units < 10:
        return ngettext(
            "Only %(count)s left",
            "Only %(count)s left",
            available_units,
        ) % {
            "count": available_units,
        }

    return str(
        _("In stock")
    )
