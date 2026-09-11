from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.utils.translation import gettext_lazy as _

from business.models import BusinessOfferSelection
from orders.models import Order, OrderLine
from pricing.models import CommercialPrice
from products.localization import translated_product_name
from products.models import Product


_REASON_LABELS = {
    CommercialPrice.Reason.SHORT_DATED: _("Short dated"),
    CommercialPrice.Reason.DAMAGED_PACKAGE: _("Damaged package"),
    CommercialPrice.Reason.PROMOTION: _("Promotion"),
    CommercialPrice.Reason.OTHER: _("Other"),
}


@dataclass(frozen=True, slots=True)
class BusinessOrderLinePresentation:
    catalog_label: str
    offer_label: str | None
    price_label: str | None


def business_product_catalog_label(
    product: Product,
    *,
    language_code: str,
) -> str:
    return (
        f"{product.code_label} · "
        f"{translated_product_name(product, language_code=language_code)} · "
        f"{product.unit_weight_label}"
    )


def business_order_line_presentation(
    line: OrderLine,
    *,
    language_code: str,
    currency: str,
) -> BusinessOrderLinePresentation:
    return BusinessOrderLinePresentation(
        catalog_label=business_product_catalog_label(
            line.product,
            language_code=language_code,
        ),
        offer_label=_business_offer_label(
            line
        ),
        price_label=_business_price_label(
            line.unit_price_snapshot,
            currency=currency,
        ),
    )


def _business_offer_label(
    line: OrderLine,
) -> str | None:
    try:
        selection = (
            line.business_offer_selection
        )
    except BusinessOfferSelection.DoesNotExist:
        return None

    if selection.commercial_price_id is None:
        return None

    commercial_price = (
        selection.commercial_price
    )

    if commercial_price is None:
        return None

    if commercial_price.reason:
        return str(
            _REASON_LABELS.get(
                commercial_price.reason,
                _("Special offer"),
            )
        )

    if commercial_price.is_batch_specific:
        return str(
            _("Special offer")
        )

    return None


def _business_price_label(
    price: Decimal | None,
    *,
    currency: str,
) -> str | None:
    if price is None:
        return None

    if currency == Order.Currency.EUR:
        return f"€{price:.2f}"

    return f"{price:.2f} {currency}"
