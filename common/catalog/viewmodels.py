from __future__ import annotations

from dataclasses import dataclass

from common.ui import UiText


@dataclass(frozen=True, slots=True)
class CatalogOfferVM:
    """Presentation contract for one selectable catalog offer.

    Portal-specific presentation code decides labels and badges.

    The shared contract only defines the stable shape consumed by catalog UI
    code.
    """

    commercial_price_id: int | None
    batch_id: int | None
    kind: str
    label: str
    badge_label: str | None
    price_label: str | None
    available_units: int

    def as_dict(self) -> dict[str, object]:
        return {
            "commercial_price_id": self.commercial_price_id,
            "batch_id": self.batch_id,
            "kind": self.kind,
            "label": self.label,
            "badge_label": self.badge_label,
            "price_label": self.price_label,
            "available_units": self.available_units,
        }


@dataclass(frozen=True, slots=True)
class ProductCardVM:
    """Presentation contract for one product card in a product list view."""

    product_id: int
    name: str
    package_label: str
    badge_label: str | None
    primary_action: UiText
    secondary_action: UiText | None = None
    offers: tuple[CatalogOfferVM, ...] = ()

    def catalog_payload(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "offers": [
                offer.as_dict()
                for offer in self.offers
            ],
        }
