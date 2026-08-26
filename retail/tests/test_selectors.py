from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import InventoryBatch
from retail.selectors import (
    get_batch_for_batch_offer,
    list_batches_for_product_offer,
)
from retail.tests.factories import (
    retail_batch_offer_factory,
    retail_inventory_batch_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_product_offer_returns_eligible_product_batches():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        quantity=10,
        best_before=today + timedelta(days=30),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    )

    assert batches == [batch]


@pytest.mark.django_db
def test_product_offer_excludes_batch_with_enabled_batch_offer():
    today = timezone.localdate()
    product = retail_product_factory()

    product_offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    ordinary_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    clearance_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-002",
        best_before=today + timedelta(days=10),
    )

    retail_batch_offer_factory(
        batch=clearance_batch,
        enabled=True,
        price=Decimal("3.90"),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=product_offer,
            today=today,
        )
    )

    assert batches == [ordinary_batch]


@pytest.mark.django_db
def test_product_offer_includes_batch_with_disabled_batch_offer():
    today = timezone.localdate()
    product = retail_product_factory()

    product_offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    retail_batch_offer_factory(
        batch=batch,
        enabled=False,
        price=Decimal("3.90"),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=product_offer,
            today=today,
        )
    )

    assert batches == [batch]


@pytest.mark.django_db
def test_product_offer_returns_batches_in_fefo_order():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    later_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-002",
        best_before=today + timedelta(days=60),
    )

    earlier_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=20),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    )

    assert batches == [
        earlier_batch,
        later_batch,
    ]


@pytest.mark.django_db
def test_product_offer_excludes_depleted_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        quantity=10,
    )
    batch.adjust_quantity(quantity=0)

    assert batch.status == InventoryBatch.Status.DEPLETED

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_excludes_closed_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
    )
    batch.close()

    assert batch.status == InventoryBatch.Status.CLOSED

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_excludes_expired_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    batch.best_before = today - timedelta(days=1)
    batch.save(update_fields=["best_before", "updated_at"])

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_excludes_batch_expiring_today():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    batch.best_before = today
    batch.save(update_fields=["best_before", "updated_at"])

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_does_not_return_batches_for_other_product():
    today = timezone.localdate()

    product = retail_product_factory(
        name="Product A",
    )
    other_product = retail_product_factory(
        name="Product B",
    )

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    retail_inventory_batch_factory(
        product=other_product,
        today=today,
        batch_id="RET-OTHER",
    )

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_disabled_product_offer_has_no_batch_pool():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=False,
        price=Decimal("6.90"),
    )

    retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
    )

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_batch_offer_returns_exact_configured_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    batch = get_batch_for_batch_offer(
        offer=offer,
        today=today,
    )

    assert batch == offer.batch


@pytest.mark.django_db
def test_batch_offer_never_falls_through_to_another_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offered_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
    )

    retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-002",
    )

    offer = retail_batch_offer_factory(
        batch=offered_batch,
        enabled=True,
        price=Decimal("3.90"),
    )

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        == offered_batch
    )


@pytest.mark.django_db
def test_disabled_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=False,
        price=Decimal("3.90"),
    )

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )


@pytest.mark.django_db
def test_depleted_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    offer.batch.adjust_quantity(quantity=0)

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )


@pytest.mark.django_db
def test_closed_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    offer.batch.close()

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )


@pytest.mark.django_db
def test_expired_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    offer.batch.best_before = today - timedelta(days=1)
    offer.batch.save(
        update_fields=[
            "best_before",
            "updated_at",
        ]
    )

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )
