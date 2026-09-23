from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from products.models import Product


class CatalogOfferKind(StrEnum):
    STANDARD = "standard"
    BATCH = "batch"


@dataclass(frozen=True, slots=True)
class CatalogOffer:
    """One channel-approved commercial choice for a catalog product.

    This contract describes commercial semantics, not portal presentation.

    `commercial_price_id` is the durable pricing identity for every offer.

    `price` is optional because a standard BUSINESS offer may deliberately
    be unpriced.

    `batch_id` is present only when the commercial choice is tied to one
    exact physical batch.
    """

    kind: CatalogOfferKind
    commercial_price_id: int
    batch_id: int | None
    reason: str | None
    price: Decimal | None
    currency: str
    available_units: int

    @property
    def is_standard(self) -> bool:
        return self.kind == CatalogOfferKind.STANDARD

    @property
    def is_batch_specific(self) -> bool:
        return self.kind == CatalogOfferKind.BATCH


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    """One product exposed by a sales-channel catalog policy."""

    product: Product
    available_units: int
    offers: tuple[CatalogOffer, ...]
