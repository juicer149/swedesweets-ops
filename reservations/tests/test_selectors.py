from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from inventory.services import create_batch
from orders.models import Allocation, Order, OrderLine
from products.models import Product
from reservations.selectors import (
    active_reserved_quantities_by_batch_pk,
    active_reserved_quantity_for_batch_pk,
)


@pytest.mark.django_db
def test_active_reserved_quantity_is_zero_without_allocations(
    product: Product,
):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    assert (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
        == 0
    )


@pytest.mark.django_db
def test_unexpired_temporary_allocation_is_active(
    product: Product,
):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=7,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=7,
    )

    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=7,
        reserved_until=timezone.now() + timedelta(minutes=35),
    )

    assert (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
        == 7
    )


@pytest.mark.django_db
def test_expired_temporary_allocation_is_not_active(
    product: Product,
):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=7,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=7,
    )

    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=7,
        reserved_until=timezone.now() - timedelta(seconds=1),
    )

    assert (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
        == 0
    )


@pytest.mark.django_db
def test_non_expiring_reserved_allocation_is_active(
    product: Product,
):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=4,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=4,
    )

    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=4,
        reserved_until=None,
    )

    assert (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
        == 4
    )


@pytest.mark.django_db
def test_cancelled_allocation_is_not_active(
    product: Product,
):
    batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=4,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=4,
    )

    allocation = Allocation.objects.create(
        order=order,
        order_line=line,
        batch=batch,
        quantity=4,
    )
    allocation.cancel()

    assert (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
        == 0
    )


@pytest.mark.django_db
def test_active_reserved_quantities_are_grouped_by_batch(
    product: Product,
):
    first_batch = create_batch(
        batch_id="A-001",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=30),
        location="Shelf A1",
    )
    second_batch = create_batch(
        batch_id="A-002",
        product=product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A2",
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=5,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=5,
    )

    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=first_batch,
        quantity=3,
    )
    Allocation.objects.create(
        order=order,
        order_line=line,
        batch=second_batch,
        quantity=2,
    )

    assert active_reserved_quantities_by_batch_pk(
        batch_pks=[
            first_batch.pk,
            second_batch.pk,
        ],
    ) == {
        first_batch.pk: 3,
        second_batch.pk: 2,
    }
