from __future__ import annotations

import pytest

from customers.selectors import (
    get_customer_order_summary,
    list_customers,
)
from orders.selectors import list_customer_orders
from orders.models import Order


@pytest.mark.django_db
def test_list_customers_defaults_to_name_order(customer, other_customer):
    customers = list(list_customers())

    assert customers == [
        customer,
        other_customer,
    ]


@pytest.mark.django_db
def test_list_customers_can_sort_by_email(customer, other_customer):
    customers = list(list_customers(sort="email"))

    assert customers == [
        other_customer,
        customer,
    ]


@pytest.mark.django_db
def test_list_customers_ignores_invalid_sort(customer, other_customer):
    customers = list(list_customers(sort="not-a-sort"))

    assert customers == [
        customer,
        other_customer,
    ]


@pytest.mark.django_db
def test_list_customer_orders_returns_only_customer_orders(customer, other_customer):
    first = Order.objects.create(customer=customer)
    second = Order.objects.create(customer=customer)
    other = Order.objects.create(customer=other_customer)

    orders = list_customer_orders(customer=customer)

    assert first in orders
    assert second in orders
    assert other not in orders


@pytest.mark.django_db
def test_get_customer_order_summary_is_empty_without_orders(customer):
    summary = get_customer_order_summary(customer=customer)

    assert summary.total_orders == 0
    assert summary.placed_orders == 0
    assert summary.packed_orders == 0
    assert summary.delivered_orders == 0
    assert summary.cancelled_orders == 0
    assert summary.last_ordered_at is None


@pytest.mark.django_db
def test_get_customer_order_summary_counts_orders_by_status(customer):
    placed = Order.objects.create(customer=customer)
    placed.mark_as_placed()

    packed = Order.objects.create(customer=customer)
    packed.mark_as_placed()
    packed.mark_as_packed()

    delivered = Order.objects.create(customer=customer)
    delivered.mark_as_placed()
    delivered.mark_as_packed()
    delivered.mark_as_delivered()

    cancelled = Order.objects.create(customer=customer)
    cancelled.cancel(reason=Order.CancelReason.CUSTOMER_REQUEST)

    summary = get_customer_order_summary(customer=customer)

    assert summary.total_orders == 4
    assert summary.placed_orders == 1
    assert summary.packed_orders == 1
    assert summary.delivered_orders == 1
    assert summary.cancelled_orders == 1
    assert summary.last_ordered_at is not None
