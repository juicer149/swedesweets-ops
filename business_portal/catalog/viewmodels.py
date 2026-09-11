from __future__ import annotations

from collections.abc import Iterable

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

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

    return ProductCardVM(
        product_id=product.id,
        name=product_name,
        package_label=product.unit_weight_label,
        badge_label=None,
        image_url=_product_image_url(
            product
        ),
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
            label=str(_("Standard")),
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


def _product_image_url(
    product,
) -> str | None:
    profile = getattr(
        product,
        "profile",
        None,
    )

    if profile is None:
        return None

    image_url = (
        profile.image_url or ""
    ).strip()

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
        return str(
            _("Only %(count)s left")
        ) % {
            "count": available_units,
        }

    return str(
        _("In stock")
    )
