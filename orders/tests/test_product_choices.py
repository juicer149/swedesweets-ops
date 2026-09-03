from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from customers.tests.factories import customer_factory
from inventory.models import InventoryBatch
from inventory.services import create_batch
from inventory.tests.factories import batch_factory
from orders.models import (
    Allocation,
    Order,
    OrderLine,
)
from orders.product_choices import build_product_choice_context
from products.tests.factories import product_factory


TODAY = timezone.localdate()


def _stock_product(
    *,
    product,
    quantity: int,
    batch_id: str,
    best_before,
    location: str,
):
    return batch_factory(
        product=product,
        quantity=quantity,
        batch_id=batch_id,
        best_before=best_before,
        location=location,
        today=TODAY,
    )


def _stock_standard_products(
    *,
    apple,
    banana,
) -> None:
    _stock_product(
        product=apple,
        quantity=100,
        batch_id="A-001",
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
    )
    _stock_product(
        product=apple,
        quantity=50,
        batch_id="A-002",
        best_before=TODAY + timedelta(days=90),
        location="Shelf A2",
    )
    _stock_product(
        product=banana,
        quantity=80,
        batch_id="B-001",
        best_before=TODAY + timedelta(days=75),
        location="Shelf B1",
    )


@pytest.mark.django_db
def test_build_product_choice_context_includes_only_orderable_products():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )
    banana = product_factory(
        brand="Generic",
        name="Banana",
        weight_per_unit=6000,
        internal_number=2,
    )
    inactive_product = product_factory(
        brand="Generic",
        name="Inactive",
        weight_per_unit=7000,
        internal_number=3,
    )
    inactive_product.active = False
    inactive_product.save(
        update_fields=["active"],
    )

    _stock_standard_products(
        apple=apple,
        banana=banana,
    )

    context = build_product_choice_context()

    products = list(context.queryset)

    assert apple in products
    assert banana in products
    assert inactive_product not in products

    assert (
        context.available_units_by_product_id[
            apple.id
        ]
        == 150
    )
    assert (
        context.available_units_by_product_id[
            banana.id
        ]
        == 80
    )


@pytest.mark.django_db
def test_build_product_choice_context_excludes_product_with_only_expired_stock():
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=100,
        best_before=TODAY,
        location="Shelf A1",
        today=TODAY,
        allow_non_future_best_before=True,
    )

    context = build_product_choice_context()

    assert list(context.queryset) == []

    assert (
        apple.id
        not in context.available_units_by_product_id
    )


@pytest.mark.django_db
def test_build_product_choice_context_includes_existing_order_product_even_if_inactive():
    customer = customer_factory()
    inactive_product = product_factory(
        brand="Generic",
        name="Inactive",
        weight_per_unit=7000,
        internal_number=3,
    )
    inactive_product.active = False
    inactive_product.save(
        update_fields=["active"],
    )

    order = Order.objects.create(
        customer=customer,
        status=Order.Status.DRAFT,
    )
    order.lines.create(
        product=inactive_product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
    )

    context = build_product_choice_context(
        order=order,
    )

    assert list(context.queryset) == [
        inactive_product,
    ]

    assert (
        inactive_product.id
        not in context.available_units_by_product_id
    )


@pytest.mark.django_db
def test_build_product_choice_context_does_not_add_draft_quantity_to_available_stock():
    customer = customer_factory()
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    _stock_product(
        product=apple,
        quantity=3,
        batch_id="A-DRAFT-AVAILABLE",
        best_before=TODAY + timedelta(days=30),
        location="Shelf A1",
    )

    draft = Order.objects.create(
        customer=customer,
        status=Order.Status.DRAFT,
    )

    OrderLine.objects.create(
        order=draft,
        product=apple,
        quantity=13,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=13,
    )

    context = build_product_choice_context(
        order=draft,
    )

    assert (
        context.available_units_by_product_id[
            apple.id
        ]
        == 3
    )

    assert (
        context.queryset
        .filter(
            pk=apple.pk,
        )
        .exists()
    )


@pytest.mark.django_db
def test_build_product_choice_context_adds_placed_order_quantity_back():
    customer = customer_factory()
    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )
    banana = product_factory(
        brand="Generic",
        name="Banana",
        weight_per_unit=6000,
        internal_number=2,
    )

    _stock_standard_products(
        apple=apple,
        banana=banana,
    )

    order = Order.objects.create(
        customer=customer,
    )
    order.mark_as_placed()

    line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=10,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=10,
    )

    batch = (
        InventoryBatch.objects
        .filter(
            product=apple,
        )
        .order_by(
            "best_before",
            "batch_id",
        )
        .first()
    )

    assert batch is not None

    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=10,
    )

    context = build_product_choice_context(
        order=order,
    )

    assert (
        context.available_units_by_product_id[
            apple.id
        ]
        == 150
    )

    assert (
        context.queryset
        .filter(
            pk=apple.pk,
        )
        .exists()
    )
