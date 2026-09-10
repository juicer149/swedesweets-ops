from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from common.catalog.contracts import CatalogProduct
from common.catalog.viewmodels import CatalogOfferVM
from common.detail_cards import (
    DetailCard,
    DetailHeader,
    DetailPanel,
)
from products.localization import translated_product_name
from products.models import ProductProfile

from business_portal.catalog.viewmodels import (
    build_business_offer_viewmodel,
)


@dataclass(frozen=True, slots=True)
class BusinessCatalogProductDetailContext:
    catalog_product: CatalogProduct
    product_name: str
    profile: ProductProfile | None
    offers: tuple[CatalogOfferVM, ...]
    detail_card: DetailCard
    title: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "catalog_product": self.catalog_product,
            "product": self.catalog_product.product,
            "product_name": self.product_name,
            "profile": self.profile,
            "offers": self.offers,
            "detail_card": self.detail_card,
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

    profile = getattr(
        product,
        "profile",
        None,
    )

    offers = tuple(
        build_business_offer_viewmodel(
            offer
        )
        for offer in catalog_product.offers
    )

    return BusinessCatalogProductDetailContext(
        catalog_product=catalog_product,
        product_name=product_name,
        profile=profile,
        offers=offers,
        detail_card=DetailCard(
            header=DetailHeader(
                eyebrow=_("Catalog"),
                title=product_name,
            ),
            panels=(
                DetailPanel(
                    key="product",
                    label=_("Product"),
                    summary=product.unit_weight_label,
                    body_template=(
                        "business_portal/catalog/includes/"
                        "detail_panel_product.html"
                    ),
                    icon="box",
                    is_active=True,
                ),
                DetailPanel(
                    key="offers",
                    label=_("Offers"),
                    summary=_("%(count)s available")
                    % {
                        "count": len(offers),
                    },
                    body_template=(
                        "business_portal/catalog/includes/"
                        "detail_panel_offers.html"
                    ),
                    icon="cart",
                    is_active=False,
                ),
            ),
        ),
        title=product_name,
        cancel_url=reverse(
            "business_portal:catalog"
        ),
    )
