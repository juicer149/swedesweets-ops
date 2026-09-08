from __future__ import annotations

from dataclasses import dataclass

from common.ui import UiText


@dataclass(frozen=True, slots=True)
class ProductCardVM:
    """Presentation contract for one product card in a product list view."""

    product_id: int
    name: str
    package_label: str
    badge_label: str | None
    primary_action: UiText
    secondary_action: UiText | None = None
