from __future__ import annotations

import pytest

from customers.services import create_customer
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


@pytest.fixture
def customer():
    return create_customer(
        name="Ica Ugglebo",
        email="ICA@EXAMPLE.SE",
        phone_number="+46 123-456-789",
        country="FR",
        city="Paris",
        address_line="Example Street 1",
    )
