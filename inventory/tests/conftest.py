from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest

from inventory.models import InventoryBatch
from inventory.tests.factories import batch_factory as make_batch
from products.models import Product
from products.tests.factories import product_factory


TODAY = date(2026, 5, 14)

BatchFactory = Callable[..., InventoryBatch]


@pytest.fixture
def apple() -> Product:
    return product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
    )


@pytest.fixture
def banana() -> Product:
    return product_factory(
        brand="Generic",
        name="Banana",
        weight_per_unit=6000,
    )


@pytest.fixture
def inactive_product() -> Product:
    product = product_factory(
        brand="Generic",
        name="Inactive Product",
        weight_per_unit=7000,
    )
    product.active = False
    product.save(update_fields=["active"])
    return product


@pytest.fixture
def batch_factory() -> BatchFactory:
    def factory(
        *,
        product: Product,
        batch_id: str = "A-001",
        quantity: int = 10,
        best_before: date | None = None,
        location: str = "Shelf A1",
    ) -> InventoryBatch:
        return make_batch(
            product=product,
            batch_id=batch_id,
            quantity=quantity,
            best_before=best_before,
            location=location,
            today=TODAY,
        )

    return factory


@pytest.fixture
def stocked_inventory(
    apple: Product,
    banana: Product,
    batch_factory: BatchFactory,
):
    apple_early = batch_factory(
        product=apple,
        batch_id="A-001",
        quantity=100,
        best_before=date(2026, 6, 1),
        location="Shelf A1",
    )
    apple_late = batch_factory(
        product=apple,
        batch_id="A-002",
        quantity=50,
        best_before=date(2026, 7, 1),
        location="Shelf A2",
    )
    banana_batch = batch_factory(
        product=banana,
        batch_id="B-001",
        quantity=80,
        best_before=date(2026, 6, 15),
        location="Shelf B1",
    )

    return {
        "apple_early": apple_early,
        "apple_late": apple_late,
        "banana": banana_batch,
    }
