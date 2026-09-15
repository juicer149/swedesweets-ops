from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from customers.tests.factories import customer_factory
from inventory.tests.factories import batch_factory
from ops_portal.models import PickChecklistMark
from ops_portal.orders.services import pack_order_and_clear_checklist
from orders.errors import InvalidOrderOperation
from orders.models import Allocation, Order, OrderLine
from products.tests.factories import product_factory


TODAY = timezone.localdate()
BEST_BEFORE = TODAY + timedelta(days=60)


@pytest.mark.django_db
def test_pack_order_and_clear_checklist_consumes_reservations_and_clears_marks():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    batch = batch_factory(
        product=apple,
        quantity=10,
        batch_id="A-001",
        best_before=BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    order = Order.objects.create(customer=customer)
    order.mark_as_placed()

    order_line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=3,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=3,
    )

    allocation = Allocation.objects.create(
        order=order,
        order_line=order_line,
        batch=batch,
        quantity=3,
        status=Allocation.Status.RESERVED,
    )

    mark = PickChecklistMark.objects.create(
        allocation=allocation,
    )

    packed_order = pack_order_and_clear_checklist(
        order=order,
    )

    allocation.refresh_from_db()
    batch.refresh_from_db()

    assert packed_order.status == Order.Status.PACKED
    assert allocation.status == Allocation.Status.CONSUMED
    assert batch.quantity == 7

    assert not PickChecklistMark.objects.filter(
        pk=mark.pk,
    ).exists()


@pytest.mark.django_db
def test_pack_order_and_clear_checklist_rolls_back_on_pack_failure():
    customer = customer_factory()

    order = Order.objects.create(customer=customer)
    order.mark_as_placed()

    # No Allocation rows exist for this order, so fulfillment.pack_order's
    # preparation step must raise before anything is persisted - including
    # any checklist mark cleanup, since the whole wrapper is one atomic
    # transaction.
    with pytest.raises(InvalidOrderOperation):
        pack_order_and_clear_checklist(
            order=order,
        )

    order.refresh_from_db()

    assert order.status == Order.Status.PLACED
