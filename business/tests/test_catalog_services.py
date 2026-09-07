from __future__ import annotations

import pytest
from datetime import timedelta

from business.services import (
    add_product_to_draft_order,
)
from inventory.services import create_batch
from orders.errors import InvalidOrderOperation
from orders.models import Order
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
)
from business.tests.conftest import TODAY


@pytest.mark.django_db
def test_add_product_to_draft_order_creates_draft_and_line(
    customer,
    apple,
    stocked_inventory,
):
    order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    assert order.channel == Order.Channel.BUSINESS
    assert order.status == Order.Status.DRAFT
    assert order.customer == customer

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 1


@pytest.mark.django_db
def test_add_product_to_draft_order_increments_existing_product(
    customer,
    apple,
    stocked_inventory,
):
    first_order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    second_order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    assert second_order.pk == first_order.pk
    assert second_order.lines.count() == 1

    line = second_order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 2


@pytest.mark.django_db
def test_add_product_to_draft_order_preserves_other_products(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    updated = add_product_to_draft_order(
        customer=customer,
        product=banana,
    )

    assert updated.pk == order.pk

    assert list(
        updated.lines
        .order_by("product_id")
        .values_list(
            "product_id",
            "quantity_in_units",
        )
    ) == [
        (
            apple.id,
            1,
        ),
        (
            banana.id,
            1,
        ),
    ]


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_inactive_product(
    customer,
    apple,
    stocked_inventory,
):
    apple.active = False
    apple.save(
        update_fields=[
            "active",
            "updated_at",
        ],
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="product is not available for business ordering",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_unavailable_product(
    customer,
    apple,
):
    with pytest.raises(
        InvalidOrderOperation,
        match="only 0 units are currently available",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_quantity_above_available_stock(
    customer,
    apple,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=3,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="only 3 units are currently available",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
            quantity=4,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_quantity_above_order_limit(
    customer,
    apple,
    monkeypatch,
):
    monkeypatch.setattr(
        "business.services.orderable_quantity_by_product_id",
        lambda: {
            apple.id: (
                MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                + 100
            ),
        },
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="maximum quantity per product",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
            quantity=(
                MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                + 1
            ),
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_non_positive_quantity(
    customer,
    apple,
):
    with pytest.raises(
        InvalidOrderOperation,
        match="quantity must be positive",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
            quantity=0,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()
