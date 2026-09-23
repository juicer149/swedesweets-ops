from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from customers.models import Customer
from orders.datatypes import BuyerInput
from pricing.models import CommercialPrice
from products.models import Product


@dataclass(frozen=True, slots=True)
class ResolvedOrderLine:
    """Order line resolved by the calling sales channel.

    The shared order domain does not decide:

    - how a product was selected
    - whether stock must exist
    - which commercial offer supplied the price
    - how external quantity units were converted

    Those decisions must already have been made by the caller.

    `commercial_offer` records which commercial alternative the line came
    from. It is temporarily optional while channels migrate to explicit
    offers; orders validates it whenever it is supplied.
    """

    product: Product
    quantity_in_units: int
    unit_price_snapshot: Decimal | None = None
    commercial_offer: CommercialPrice | None = None


@dataclass(frozen=True, slots=True)
class OrderDraft:
    """Resolved data required to persist a new draft order."""

    channel: str
    currency: str
    buyer: BuyerInput
    lines: tuple[ResolvedOrderLine, ...]
    customer: Customer | None = None
