from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from customers.tests.factories import customer_factory
from inventory.tests.factories import batch_factory
from ops_portal.models import PickChecklistMark
from ops_portal.orders.services import (
    pack_order_and_clear_checklist,
    update_placed_order_and_preserve_checklist,
)
from orders.datatypes import OrderLineInput
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from reservations.models import Allocation
from products.tests.factories import product_factory
from products.units import OrderUnit


TODAY = timezone.localdate()
BEST_BEFORE = TODAY + timedelta(days=60)


def _place_order_with_line(
    *,
    customer,
    product,
    batch,
    quantity: int,
) -> tuple[Order, OrderLine, Allocation]:
    order = Order.objects.create(customer=customer)
    order.mark_as_placed()

    order_line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
    )

    allocation = Allocation.objects.create(
        order=order,
        order_line=order_line,
        batch=batch,
        quantity=quantity,
        status=Allocation.Status.RESERVED,
    )

    return order, order_line, allocation


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

    order, _order_line, allocation = _place_order_with_line(
        customer=customer,
        product=apple,
        batch=batch,
        quantity=3,
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


@pytest.mark.django_db
def test_update_placed_order_preserves_mark_for_unchanged_quantity():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    batch = batch_factory(
        product=apple,
        quantity=20,
        batch_id="A-001",
        best_before=BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    order, _order_line, old_allocation = _place_order_with_line(
        customer=customer,
        product=apple,
        batch=batch,
        quantity=3,
    )

    PickChecklistMark.objects.create(
        allocation=old_allocation,
    )

    # Edit that keeps the same product at the same total quantity - the
    # line's quantity is unchanged, only the underlying Allocation is
    # rebuilt by update_placed_order under the hood. Only one batch
    # exists for this product, so the rebuild deterministically lands
    # on the same batch again.
    updated_order = update_placed_order_and_preserve_checklist(
        order=order,
        lines=[
            OrderLineInput.units(
                quantity=3,
                product=apple,
            ),
        ],
    )

    new_allocation = Allocation.objects.get(
        order=updated_order,
        status=Allocation.Status.RESERVED,
    )

    assert new_allocation.pk != old_allocation.pk
    assert PickChecklistMark.objects.filter(
        allocation=new_allocation,
    ).exists()


@pytest.mark.django_db
def test_update_placed_order_clears_mark_when_quantity_changes():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    batch = batch_factory(
        product=apple,
        quantity=20,
        batch_id="A-001",
        best_before=BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    order, order_line, allocation = _place_order_with_line(
        customer=customer,
        product=apple,
        batch=batch,
        quantity=3,
    )

    PickChecklistMark.objects.create(
        allocation=allocation,
    )

    # Same product, different quantity - staff have not verified the new
    # amount, so the old checkmark must not survive even though it's the
    # same (product, batch) pairing.
    updated_order = update_placed_order_and_preserve_checklist(
        order=order,
        lines=[
            OrderLineInput.units(
                quantity=5,
                product=apple,
            ),
        ],
    )

    new_allocation = Allocation.objects.get(
        order=updated_order,
        status=Allocation.Status.RESERVED,
    )

    assert new_allocation.quantity == 5
    assert not PickChecklistMark.objects.filter(
        allocation=new_allocation,
    ).exists()


@pytest.mark.django_db
def test_update_placed_order_clears_mark_when_product_is_removed():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    pear = product_factory(
        brand="Generic",
        name="Pear",
        weight_per_unit=4000,
        internal_number=2,
    )

    apple_batch = batch_factory(
        product=apple,
        quantity=20,
        batch_id="A-001",
        best_before=BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    batch_factory(
        product=pear,
        quantity=20,
        batch_id="B-001",
        best_before=BEST_BEFORE,
        location="Shelf B1",
        today=TODAY,
    )

    order, _order_line, allocation = _place_order_with_line(
        customer=customer,
        product=apple,
        batch=apple_batch,
        quantity=3,
    )

    PickChecklistMark.objects.create(
        allocation=allocation,
    )

    # Apple dropped entirely, replaced by an unrelated product - no
    # allocation for apple exists afterward, so there is nothing left
    # to carry a mark onto.
    updated_order = update_placed_order_and_preserve_checklist(
        order=order,
        lines=[
            OrderLineInput.units(
                quantity=2,
                product=pear,
            ),
        ],
    )

    assert not Allocation.objects.filter(
        order=updated_order,
        batch__product=apple,
    ).exists()

    assert not PickChecklistMark.objects.filter(
        allocation__order=updated_order,
    ).exists()


@pytest.mark.django_db
def test_update_placed_order_preserves_split_batch_marks_individually():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    # Two batches, exactly large enough that a 75-unit order deterministically
    # splits 50 from the first (earlier best_before, FEFO) and 25 from the
    # second - mirrors the two-batch checklist scenario directly.
    batch_a = batch_factory(
        product=apple,
        quantity=50,
        batch_id="A-001",
        best_before=BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    batch_b = batch_factory(
        product=apple,
        quantity=50,
        batch_id="A-002",
        best_before=BEST_BEFORE + timedelta(days=5),
        location="Shelf A2",
        today=TODAY,
    )

    order = Order.objects.create(customer=customer)
    order.mark_as_placed()

    order_line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=75,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=75,
    )

    allocation_a = Allocation.objects.create(
        order=order,
        order_line=order_line,
        batch=batch_a,
        quantity=50,
        status=Allocation.Status.RESERVED,
    )

    allocation_b = Allocation.objects.create(
        order=order,
        order_line=order_line,
        batch=batch_b,
        quantity=25,
        status=Allocation.Status.RESERVED,
    )

    # Only the 50-unit (batch A) line has been physically checked off.
    PickChecklistMark.objects.create(
        allocation=allocation_a,
    )

    # Same total quantity (75) - the deterministic FEFO split reproduces the
    # same two batches, so the checked line should stay checked and the
    # never-checked line should simply remain unchecked.
    updated_order = update_placed_order_and_preserve_checklist(
        order=order,
        lines=[
            OrderLineInput.units(
                quantity=75,
                product=apple,
            ),
        ],
    )

    new_allocations = list(
        Allocation.objects.filter(
            order=updated_order,
            status=Allocation.Status.RESERVED,
        ).select_related("batch")
    )

    assert len(new_allocations) == 2

    new_allocation_a = next(
        allocation
        for allocation in new_allocations
        if allocation.batch_id == batch_a.id
    )
    new_allocation_b = next(
        allocation
        for allocation in new_allocations
        if allocation.batch_id == batch_b.id
    )

    assert PickChecklistMark.objects.filter(
        allocation=new_allocation_a,
    ).exists()
    assert not PickChecklistMark.objects.filter(
        allocation=new_allocation_b,
    ).exists()


@pytest.mark.django_db
def test_update_placed_order_clears_all_split_batch_marks_on_quantity_change():
    customer = customer_factory()

    apple = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
        internal_number=1,
    )

    batch_a = batch_factory(
        product=apple,
        quantity=60,
        batch_id="A-001",
        best_before=BEST_BEFORE,
        location="Shelf A1",
        today=TODAY,
    )

    batch_factory(
        product=apple,
        quantity=60,
        batch_id="A-002",
        best_before=BEST_BEFORE + timedelta(days=5),
        location="Shelf A2",
        today=TODAY,
    )

    order = Order.objects.create(customer=customer)
    order.mark_as_placed()

    order_line = OrderLine.objects.create(
        order=order,
        product=apple,
        quantity=75,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=75,
    )

    allocation_a = Allocation.objects.create(
        order=order,
        order_line=order_line,
        batch=batch_a,
        quantity=50,
        status=Allocation.Status.RESERVED,
    )

    Allocation.objects.create(
        order=order,
        order_line=order_line,
        batch=batch_a,  # placeholder, replaced below to keep two rows distinct
        quantity=25,
        status=Allocation.Status.RESERVED,
    )

    # Only the first (checked) line is marked - matches the scenario where
    # a packer checked the 50-unit line but not the 25-unit one.
    PickChecklistMark.objects.create(
        allocation=allocation_a,
    )

    # Total quantity for this product changes (75 -> 90) - even though the
    # checked line's batch may well reappear in the new split, the mark
    # must not survive: the packer has not yet verified the new quantity.
    updated_order = update_placed_order_and_preserve_checklist(
        order=order,
        lines=[
            OrderLineInput.units(
                quantity=90,
                product=apple,
            ),
        ],
    )

    assert not PickChecklistMark.objects.filter(
        allocation__order=updated_order,
    ).exists()
