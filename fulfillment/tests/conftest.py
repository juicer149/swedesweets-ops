from __future__ import annotations

import pytest
from django.utils import timezone

from customers.tests.factories import customer_factory
from products.models import Product
from products.tests.factories import product_factory


TODAY = timezone.localdate()


@pytest.fixture
def apple() -> Product:
    return product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )


@pytest.fixture
def customer():
    return customer_factory(
        name="Ica Ugglebo",
        email="ICA@EXAMPLE.SE",
        phone_number="+46 123-456-789",
        country="FR",
        city="Paris",
        address_line="Example Street 1",
    )
