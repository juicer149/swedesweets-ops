from __future__ import annotations

from datetime import date

import pytest

from inventory.services import create_batch
from products.models import Product
from products.services import create_product


TODAY = date(2026, 5, 14)


@pytest.fixture
def apple() -> Product:
    result = create_product(
        brand="Generic",
        name="Apple",
        weight_per_box=5000,
    )
    return result.item


@pytest.fixture
def banana() -> Product:
    result = create_product(
        brand="Generic",
        name="Banana",
        weight_per_box=6000,
    )
    return result.item


@pytest.fixture
def inactive_product() -> Product:
    result = create_product(
        brand="Generic",
        name="Inactive Product",
        weight_per_box=7000,
    )
    product = result.item
    product.active = False
    product.save(update_fields=["active"])
    return product


@pytest.fixture
def stocked_inventory(apple: Product, banana: Product):
    apple_early = create_batch(
        batch_id="A-001",
        product=apple,
        boxes=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
        today=TODAY,
    )
    apple_late = create_batch(
        batch_id="A-002",
        product=apple,
        boxes=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
        today=TODAY,
    )
    banana_batch = create_batch(
        batch_id="B-001",
        product=banana,
        boxes=80,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
        today=TODAY,
    )

    return {
        "apple_early": apple_early,
        "apple_late": apple_late,
        "banana": banana_batch,
    }
