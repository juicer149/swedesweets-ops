from __future__ import annotations

import pytest

from customers.tests.factories import customer_factory
from customer_portal.services import (
    DraftStatus,
    discard_portal_draft_order,
    save_or_clear_portal_draft_order,
)
from inventory.tests.conftest import TODAY
from inventory.tests.factories import batch_factory
from orders.datatypes import OrderLineInput
from orders.services import create_draft_order
from products.tests.factories import product_factory


@pytest.mark.django_db
def test_save_or_clear_portal_draft_order_saves_non_empty_lines():
    customer = customer_factory()
    apple = product_factory(name="Apple", weight_per_unit=5000)
    batch_factory(product=apple, today=TODAY, quantity=100)

    result = save_or_clear_portal_draft_order(
        customer=customer,
        draft_order=None,
        line_inputs=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    assert result.succeeded is True
    assert result.status == DraftStatus.SAVED
    assert result.draft_order is not None


@pytest.mark.django_db
def test_save_or_clear_portal_draft_order_clears_empty_existing_draft():
    customer = customer_factory()
    apple = product_factory(name="Apple", weight_per_unit=5000)
    batch_factory(product=apple, today=TODAY, quantity=100)

    draft_order = create_draft_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    result = save_or_clear_portal_draft_order(
        customer=customer,
        draft_order=draft_order,
        line_inputs=[],
    )

    assert result.succeeded is True
    assert result.status == DraftStatus.CLEARED
    assert result.draft_order is None


@pytest.mark.django_db
def test_save_or_clear_portal_draft_order_is_unchanged_without_draft_or_lines():
    customer = customer_factory()

    result = save_or_clear_portal_draft_order(
        customer=customer,
        draft_order=None,
        line_inputs=[],
    )

    assert result.succeeded is True
    assert result.status == DraftStatus.UNCHANGED
    assert result.draft_order is None


@pytest.mark.django_db
def test_discard_portal_draft_order_rejects_other_customer_draft():
    customer = customer_factory(email="one@example.com")
    other_customer = customer_factory(email="two@example.com")

    apple = product_factory(name="Apple", weight_per_unit=5000)
    batch_factory(product=apple, today=TODAY, quantity=100)

    draft_order = create_draft_order(
        customer=other_customer,
        lines=[
            OrderLineInput.units(product=apple, quantity=10),
        ],
    )

    result = discard_portal_draft_order(
        customer=customer,
        draft_order=draft_order,
    )

    assert result.succeeded is False
    assert result.status == DraftStatus.UNCHANGED
    assert result.errors == ("Order does not belong to the current customer.",)
