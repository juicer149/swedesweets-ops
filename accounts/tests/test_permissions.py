from __future__ import annotations

import pytest

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role, resolve_role_spec
from accounts.roles import AccountRole, StaffAccessLevel
from accounts.tests.factories import (
    customer_membership_factory,
    full_staff_user_factory,
    restricted_staff_user_factory,
    staff_account_factory,
    superuser_factory,
    user_factory,
)
from customers.models import Customer
from customers.tests.factories import customer_factory


@pytest.fixture
def user(db):
    return user_factory(
        username="user@example.com",
    )


@pytest.fixture
def customer(db) -> Customer:
    return customer_factory(
        name="Super U Les Houches",
        email="orders@example.fr",
        phone_number="+33 123456789",
        country="FR",
        city="Les Houches",
        address_line="123 Route des Sweets",
    )


@pytest.mark.django_db
def test_superuser_resolves_as_owner():
    owner = superuser_factory(
        username="owner@example.com",
    )

    assert resolve_account_role(owner) == AccountRole.OWNER

    spec = resolve_role_spec(owner)

    assert spec.can_view_staff_ops
    assert spec.can_manage_accounts
    assert spec.can_view_orders
    assert spec.can_create_orders
    assert spec.can_edit_orders
    assert spec.can_cancel_orders
    assert spec.can_pack_orders
    assert spec.can_deliver_orders
    assert spec.can_view_inventory
    assert spec.can_create_batches
    assert spec.can_edit_batches
    assert spec.can_close_batches
    assert spec.can_view_inventory_risks
    assert spec.can_view_ops_products
    assert spec.can_create_products
    assert spec.can_edit_products
    assert spec.can_view_customers
    assert spec.can_create_customers
    assert spec.can_edit_customers

    assert not spec.can_view_customer_portal
    assert not spec.can_place_customer_orders
    assert not spec.can_view_own_orders


@pytest.mark.django_db
def test_full_staff_resolves_as_full_staff():
    user = full_staff_user_factory()

    assert resolve_account_role(user) == AccountRole.FULL_STAFF

    spec = resolve_role_spec(user)

    assert spec.can_view_staff_ops
    assert spec.can_manage_accounts
    assert spec.can_view_orders
    assert spec.can_create_orders
    assert spec.can_edit_orders
    assert spec.can_cancel_orders
    assert spec.can_pack_orders
    assert spec.can_deliver_orders
    assert spec.can_view_inventory
    assert spec.can_create_batches
    assert spec.can_edit_batches
    assert spec.can_close_batches
    assert spec.can_view_inventory_risks
    assert spec.can_view_ops_products
    assert spec.can_create_products
    assert spec.can_edit_products
    assert spec.can_view_customers
    assert spec.can_create_customers
    assert spec.can_edit_customers

    assert not spec.can_view_customer_portal
    assert not spec.can_place_customer_orders
    assert not spec.can_view_own_orders


@pytest.mark.django_db
def test_restricted_staff_resolves_as_restricted_staff():
    user = restricted_staff_user_factory()

    assert resolve_account_role(user) == AccountRole.RESTRICTED_STAFF

    spec = resolve_role_spec(user)

    assert spec.can_view_staff_ops
    assert spec.can_view_orders
    assert spec.can_pack_orders
    assert spec.can_deliver_orders
    assert spec.can_view_inventory
    assert spec.can_create_batches
    assert spec.can_view_ops_products
    assert spec.can_view_customers

    assert not spec.can_manage_accounts
    assert not spec.can_create_orders
    assert not spec.can_edit_orders
    assert not spec.can_cancel_orders
    assert not spec.can_edit_batches
    assert not spec.can_close_batches
    assert not spec.can_view_inventory_risks
    assert not spec.can_create_products
    assert not spec.can_edit_products
    assert not spec.can_create_customers
    assert not spec.can_edit_customers
    assert not spec.can_view_customer_portal
    assert not spec.can_place_customer_orders
    assert not spec.can_view_own_orders


@pytest.mark.django_db
def test_customer_resolves_as_customer(user, customer):
    customer_membership_factory(
        user=user,
        customer=customer,
    )

    assert resolve_account_role(user) == AccountRole.CUSTOMER

    spec = resolve_role_spec(user)

    assert spec.can_view_customer_portal
    assert spec.can_place_customer_orders
    assert spec.can_view_own_orders

    assert not spec.can_view_staff_ops
    assert not spec.can_manage_accounts
    assert not spec.can_view_orders
    assert not spec.can_create_orders
    assert not spec.can_edit_orders
    assert not spec.can_cancel_orders
    assert not spec.can_pack_orders
    assert not spec.can_deliver_orders
    assert not spec.can_view_inventory
    assert not spec.can_create_batches
    assert not spec.can_edit_batches
    assert not spec.can_close_batches
    assert not spec.can_view_inventory_risks
    assert not spec.can_view_ops_products
    assert not spec.can_create_products
    assert not spec.can_edit_products
    assert not spec.can_view_customers
    assert not spec.can_create_customers
    assert not spec.can_edit_customers


@pytest.mark.django_db
def test_user_without_business_identity_resolves_as_unknown(user):
    assert resolve_account_role(user) == AccountRole.UNKNOWN

    spec = resolve_role_spec(user)

    assert not spec.can_view_staff_ops
    assert not spec.can_view_customer_portal
    assert not spec.can_manage_accounts
    assert not spec.can_view_orders
    assert not spec.can_create_orders
    assert not spec.can_edit_orders
    assert not spec.can_cancel_orders
    assert not spec.can_pack_orders
    assert not spec.can_deliver_orders
    assert not spec.can_view_inventory
    assert not spec.can_create_batches
    assert not spec.can_edit_batches
    assert not spec.can_close_batches
    assert not spec.can_view_inventory_risks
    assert not spec.can_view_ops_products
    assert not spec.can_create_products
    assert not spec.can_edit_products
    assert not spec.can_view_customers
    assert not spec.can_create_customers
    assert not spec.can_edit_customers
    assert not spec.can_place_customer_orders
    assert not spec.can_view_own_orders


@pytest.mark.django_db
def test_user_cannot_be_both_staff_and_customer(user, customer):
    staff_account_factory(
        user=user,
        access_level=StaffAccessLevel.RESTRICTED,
    )
    customer_membership_factory(
        user=user,
        customer=customer,
    )

    with pytest.raises(InvalidAccountIdentity):
        resolve_account_role(user)
