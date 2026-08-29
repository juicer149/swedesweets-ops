from __future__ import annotations

import pytest

from products.models import Product
from products.tests.factories import product_factory


@pytest.fixture
def product() -> Product:
    """Create a generic product for reservation integration tests."""

    return product_factory(
        brand="Generic",
        name="Reservation Product",
        weight_per_unit=5000,
    )
