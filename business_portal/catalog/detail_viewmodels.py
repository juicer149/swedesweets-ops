from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.catalog.contracts import CatalogProduct
from common.catalog.viewmodels import CatalogOfferVM
from products.localization import translated_product_name
from products.models import ProductProfile

from business_portal.catalog.viewmodels import (
    build_business_offer_viewmodel,
)


@dataclass(frozen=True, slots=True)
class BusinessCatalogProductDetailContext:
    catalog_product: CatalogProduct
    product_name: str
    category_label: str | None
    image_url: str | None
    description: str
    ingredients: str
    offers: tuple[CatalogOfferVM, ...]
    initial_offer: CatalogOfferVM
    title: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "catalog_product": self.catalog_product,
            "product": self.catalog_product.product,
            "product_name": self.product_name,
            "category_label": self.category_label,
            "image_url": self.image_url,
            "description": self.description,
            "ingredients": self.ingredients,
            "offers": self.offers,
            "initial_offer": self.initial_offer,
            "title": self.title,
            "cancel_url": self.cancel_url,
        }


def build_business_catalog_product_detail_context(
    *,
    catalog_product: CatalogProduct,
    language_code: str,
) -> BusinessCatalogProductDetailContext:
    product = catalog_product.product

    product_name = translated_product_name(
        product,
        language_code=language_code,
    )

    profile = _get_product_profile(
        product=product,
    )

    offers = tuple(
        build_business_offer_viewmodel(
            offer
        )
        for offer in catalog_product.offers
    )

    if not offers:
        raise ValueError(
            "Business catalog product must have at least one offer"
        )

    return BusinessCatalogProductDetailContext(
        catalog_product=catalog_product,
        product_name=product_name,
        category_label=_category_label(
            profile=profile,
        ),
        image_url=_image_url(
            profile=profile,
        ),
        description=_description(
            profile=profile,
        ),
        ingredients=_ingredients(
            profile=profile,
        ),
        offers=offers,
        initial_offer=offers[0],
        title=product_name,
        cancel_url=reverse(
            "business_portal:catalog"
        ),
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
    if profile is None:
        return None

    return (
        profile.image_url
        or None
    )


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
