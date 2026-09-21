from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from customers.tests.factories import customer_factory
from inventory.tests.factories import batch_factory
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
def banana() -> Product:
    return product_factory(
        brand="Generic",
        name="Banana",
        weight_per_unit=6000,
        internal_number=2,
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


@pytest.fixture
def stocked_inventory(apple: Product, banana: Product):
    return {
        "apple_early": batch_factory(
            product=apple,
            today=TODAY,
            batch_id="A-001",
            quantity=100,
            best_before=TODAY + timedelta(days=60),
            location="Shelf A1",
        ),
        "apple_late": batch_factory(
            product=apple,
            today=TODAY,
            batch_id="A-002",
            quantity=50,
            best_before=TODAY + timedelta(days=90),
            location="Shelf A2",
        ),
        "banana": batch_factory(
            product=banana,
            today=TODAY,
            batch_id="B-001",
            quantity=80,
            best_before=TODAY + timedelta(days=75),
            location="Shelf B1",
        ),
    }
