from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from customers.services import create_customer
from inventory.services import create_batch
from products.models import Product
from products.services import create_product


TODAY = timezone.localdate()

STOCK_EARLY_BEST_BEFORE = TODAY + timedelta(days=60)
STOCK_LATE_BEST_BEFORE = TODAY + timedelta(days=90)
STOCK_BANANA_BEST_BEFORE = TODAY + timedelta(days=75)


@pytest.fixture
def apple() -> Product:
    result = create_product(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )
    return result.item


@pytest.fixture
def banana() -> Product:
    result = create_product(
        brand="Generic",
        name="Banana",
        weight_per_unit=6000,
        internal_number=2,
    )
    return result.item


@pytest.fixture
def inactive_product() -> Product:
    result = create_product(
        brand="Generic",
        name="Inactive",
        weight_per_unit=7000,
        internal_number=3,
    )
    product = result.item
    product.active = False
    product.save(update_fields=["active"])
    return product


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


@pytest.fixture
def other_customer():
    return create_customer(
        name="Coop Björkvik",
        email="coop@example.se",
        phone_number="+46 987-654-321",
        country="CH",
        city="Zürich",
        address_line="Other Street 2",
    )


@pytest.fixture
def stocked_inventory(apple: Product, banana: Product):
    apple_early = create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=STOCK_EARLY_BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )
    apple_late = create_batch(
        batch_id="A-002",
        product=apple,
        quantity=50,
        best_before=STOCK_LATE_BEST_BEFORE,
        location="Shelf A2",
        today=TODAY,
    )
    banana_batch = create_batch(
        batch_id="B-001",
        product=banana,
        quantity=80,
        best_before=STOCK_BANANA_BEST_BEFORE,
        location="Shelf B1",
        today=TODAY,
    )

    return {
        "apple_early": apple_early,
        "apple_late": apple_late,
        "banana": banana_batch,
    }
