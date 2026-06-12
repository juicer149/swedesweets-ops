from __future__ import annotations

import pytest

from customers.selectors import list_customers


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
