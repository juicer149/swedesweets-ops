from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import (
    gettext_lazy as _,
)

from business_portal.catalog.viewmodels import (
    build_business_offer_viewmodel,
)
from common.catalog.contracts import (
    CatalogProduct,
)
from common.catalog.viewmodels import (
    CatalogOfferVM,
)
from common.detail_cards import (
    DetailPanel,
)
from products.localization import (
    translated_product_name,
)
from products.models import (
    ProductProfile,
)


@dataclass(frozen=True, slots=True)
class BusinessCatalogProductDetailContext:
    catalog_product: CatalogProduct
    product_name: str
    category_label: str | None
    image_url: str | None
    description: str
    ingredients: str
    offers: tuple[
        CatalogOfferVM,
        ...,
    ]
    initial_offer: CatalogOfferVM
    detail_panels: tuple[
        DetailPanel,
        ...,
    ]
    title: str
    cancel_url: str

    def as_dict(
        self,
    ) -> dict[str, object]:
        return {
            "catalog_product": (
                self.catalog_product
            ),
            "product": (
                self.catalog_product
                .product
            ),
            "product_name": (
                self.product_name
            ),
            "category_label": (
                self.category_label
            ),
            "image_url": (
                self.image_url
            ),
            "description": (
                self.description
            ),
            "ingredients": (
                self.ingredients
            ),
            "offers": self.offers,
            "initial_offer": (
                self.initial_offer
            ),
            "detail_panels": (
                self.detail_panels
            ),
            "title": self.title,
            "cancel_url": (
                self.cancel_url
            ),
        }


def build_business_catalog_product_detail_context(
    *,
    catalog_product: CatalogProduct,
    language_code: str,
) -> BusinessCatalogProductDetailContext:
    product = (
        catalog_product.product
    )

    product_name = (
        translated_product_name(
            product,
            language_code=(
                language_code
            ),
        )
    )

    profile = (
        _get_product_profile(
            product=product,
        )
    )

    offers = tuple(
        build_business_offer_viewmodel(
            offer
        )
        for offer
        in catalog_product.offers
    )

    if not offers:
        raise ValueError(
            (
                "Business catalog product "
                "must have at least one offer"
            )
        )

    description = _description(
        profile=profile
    )

    ingredients = _ingredients(
        profile=profile
    )

    return (
        BusinessCatalogProductDetailContext(
            catalog_product=(
                catalog_product
            ),
            product_name=(
                product_name
            ),
            category_label=(
                _category_label(
                    profile=profile,
                )
            ),
            image_url=(
                _image_url(
                    profile=profile,
                )
            ),
            description=description,
            ingredients=ingredients,
            offers=offers,
            initial_offer=offers[0],
            detail_panels=(
                _build_detail_panels(
                    description=description,
                    ingredients=ingredients,
                )
            ),
            title=product_name,
            cancel_url=reverse(
                "business_portal:catalog"
            ),
        )
    )


def _get_product_profile(
    *,
    product,
) -> ProductProfile | None:
    return getattr(
        product,
        "profile",
        None,
    )


def _category_label(
    *,
    profile: ProductProfile | None,
) -> str | None:
    if profile is None:
        return None

    if not profile.category:
        return None

    return str(
        profile.get_category_display()
    )


def _image_url(
    *,
    profile: ProductProfile | None,
) -> str | None:
    if (
        profile is None
        or not profile.image
    ):
        return None

    return profile.image.url


def _description(
    *,
    profile: ProductProfile | None,
) -> str:
    if profile is None:
        return ""

    return profile.description


def _ingredients(
    *,
    profile: ProductProfile | None,
) -> str:
    if profile is None:
        return ""

    return profile.ingredients


def _build_detail_panels(
    *,
    description: str,
    ingredients: str,
) -> tuple[
    DetailPanel,
    ...,
]:
    panels: list[
        DetailPanel
    ] = []

    if description:
        panels.append(
            DetailPanel(
                key="description",
                label=_(
                    "Description"
                ),
                summary=_(
                    "Product description"
                ),
                body_template=(
                    "business_portal/"
                    "catalog/includes/"
                    "detail_panel_description.html"
                ),
                is_active=True,
            )
        )

    if ingredients:
        panels.append(
            DetailPanel(
                key="ingredients",
                label=_(
                    "Ingredients"
                ),
                summary=_(
                    "Ingredients"
                ),
                body_template=(
                    "business_portal/"
                    "catalog/includes/"
                    "detail_panel_ingredients.html"
                ),
                is_active=not panels,
            )
        )

    return tuple(
        panels
    )
