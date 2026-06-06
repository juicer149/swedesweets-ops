from __future__ import annotations

import pytest

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role, resolve_role_spec
from accounts.roles import AccountRole, Capability, StaffAccessLevel
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


def _assert_allows_all(spec, capabilities: set[Capability]) -> None:
    for capability in capabilities:
        assert spec.allows(capability)


def _assert_denies_all(spec, capabilities: set[Capability]) -> None:
    for capability in capabilities:
        assert not spec.allows(capability)


STAFF_CAPABILITIES = {
    Capability.VIEW_STAFF_OPS,
    Capability.MANAGE_ACCOUNTS,

    Capability.VIEW_ORDERS,
    Capability.CREATE_ORDERS,
    Capability.EDIT_ORDERS,
    Capability.CANCEL_ORDERS,
    Capability.PACK_ORDERS,
    Capability.DELIVER_ORDERS,

    Capability.VIEW_INVENTORY,
    Capability.CREATE_BATCHES,
    Capability.EDIT_BATCHES,
    Capability.CLOSE_BATCHES,
    Capability.VIEW_INVENTORY_RISKS,

    Capability.VIEW_OPS_PRODUCTS,
    Capability.CREATE_PRODUCTS,
    Capability.EDIT_PRODUCTS,

    Capability.VIEW_CUSTOMERS,
    Capability.CREATE_CUSTOMERS,
    Capability.EDIT_CUSTOMERS,
}

RESTRICTED_STAFF_CAPABILITIES = {
    Capability.VIEW_STAFF_OPS,

    Capability.VIEW_ORDERS,
    Capability.PACK_ORDERS,
    Capability.DELIVER_ORDERS,

    Capability.VIEW_INVENTORY,
    Capability.CREATE_BATCHES,

    Capability.VIEW_OPS_PRODUCTS,
    Capability.VIEW_CUSTOMERS,
}

CUSTOMER_CAPABILITIES = {
    Capability.VIEW_CUSTOMER_PORTAL,
    Capability.PLACE_CUSTOMER_ORDERS,
    Capability.VIEW_OWN_ORDERS,
}


@pytest.mark.django_db
def test_superuser_resolves_as_owner():
    owner = superuser_factory(
        username="owner@example.com",
    )

    assert resolve_account_role(owner) == AccountRole.OWNER

    spec = resolve_role_spec(owner)

    _assert_allows_all(
        spec,
        STAFF_CAPABILITIES,
    )
    _assert_denies_all(
        spec,
        CUSTOMER_CAPABILITIES,
    )


@pytest.mark.django_db
def test_full_staff_resolves_as_full_staff():
    user = full_staff_user_factory()

    assert resolve_account_role(user) == AccountRole.FULL_STAFF

    spec = resolve_role_spec(user)

    _assert_allows_all(
        spec,
        STAFF_CAPABILITIES,
    )
    _assert_denies_all(
        spec,
        CUSTOMER_CAPABILITIES,
    )


@pytest.mark.django_db
def test_restricted_staff_resolves_as_restricted_staff():
    user = restricted_staff_user_factory()

    assert resolve_account_role(user) == AccountRole.RESTRICTED_STAFF

    spec = resolve_role_spec(user)

    _assert_allows_all(
        spec,
        RESTRICTED_STAFF_CAPABILITIES,
    )
    _assert_denies_all(
        spec,
        set(Capability)
        - RESTRICTED_STAFF_CAPABILITIES,
    )


@pytest.mark.django_db
def test_customer_resolves_as_customer(user, customer):
    customer_membership_factory(
        user=user,
        customer=customer,
    )

    assert resolve_account_role(user) == AccountRole.CUSTOMER

    spec = resolve_role_spec(user)

    _assert_allows_all(
        spec,
        CUSTOMER_CAPABILITIES,
    )
    _assert_denies_all(
        spec,
        set(Capability)
        - CUSTOMER_CAPABILITIES,
    )


@pytest.mark.django_db
def test_user_without_business_identity_resolves_as_unknown(user):
    assert resolve_account_role(user) == AccountRole.UNKNOWN

    spec = resolve_role_spec(user)

    _assert_denies_all(
        spec,
        set(Capability),
    )


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
