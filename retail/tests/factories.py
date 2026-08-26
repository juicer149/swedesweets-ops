from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from products.models import Product
from products.tests.factories import product_factory
from retail.models import RetailPostalArea


@dataclass(frozen=True)
class RetailBuyerFactoryData:
    """Valid retail buyer data used as the default test case."""

    first_name: str = "Marie"
    last_name: str = "Dupont"
    email: str = "marie@example.com"
    phone_number: str = "+33612345678"

    country: str = "FR"
    postal_code: str = "74000"
    city: str = "Annecy"
    address_line: str = "10 Rue de Test"

    def as_dict(self, **overrides: str) -> dict[str, str]:
        return asdict(self) | overrides


def retail_buyer_data(**overrides: str) -> dict[str, str]:
    return RetailBuyerFactoryData().as_dict(**overrides)


def retail_postal_area_factory(
    *,
    country_code: str = "FR",
    postal_code: str = "74000",
    city: str = "Annecy",
    enabled: bool = True,
) -> RetailPostalArea:
    return RetailPostalArea.objects.create(
        country_code=country_code,
        postal_code=postal_code,
        city=city,
        enabled=enabled,
    )


def retail_product_factory(**overrides) -> Product:
    defaults = {
        "name": "Retail Test Product",
    }

    return product_factory(**(defaults | overrides))
