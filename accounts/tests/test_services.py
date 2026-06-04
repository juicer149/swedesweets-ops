from __future__ import annotations

import pytest

from accounts.errors import AccountCreationError
from accounts.models import CustomerMembership, StaffAccount
from accounts.roles import StaffAccessLevel
from accounts.services import (
    create_customer_account,
    create_full_staff_account,
    create_restricted_staff_account,
)
from accounts.tests.factories import user_factory
from customers.models import Customer
from customers.tests.factories import customer_factory


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
def test_create_full_staff_account_creates_user_and_full_staff_account():
    result = create_full_staff_account(
        email=" FULL@EXAMPLE.COM ",
        password="safe-password",
    )

    user = result.user

    assert user.username == "full@example.com"
    assert user.email == "full@example.com"
    assert user.check_password("safe-password")

    staff_account = StaffAccount.objects.get(user=user)
    assert staff_account.access_level == StaffAccessLevel.FULL


@pytest.mark.django_db
def test_create_restricted_staff_account_creates_user_and_restricted_staff_account():
    result = create_restricted_staff_account(
        email=" restricted@example.com ",
        password="safe-password",
    )

    user = result.user

    assert user.username == "restricted@example.com"
    assert user.email == "restricted@example.com"
    assert user.check_password("safe-password")

    staff_account = StaffAccount.objects.get(user=user)
    assert staff_account.access_level == StaffAccessLevel.RESTRICTED


@pytest.mark.django_db
def test_create_customer_account_creates_user_and_customer_membership(customer):
    result = create_customer_account(
        email=" customer@example.com ",
        customer=customer,
        password="safe-password",
    )

    user = result.user

    assert user.username == "customer@example.com"
    assert user.email == "customer@example.com"
    assert user.check_password("safe-password")

    membership = CustomerMembership.objects.get(user=user)
    assert membership.customer == customer


@pytest.mark.django_db
def test_create_account_without_password_sets_unusable_password():
    result = create_restricted_staff_account(
        email="restricted@example.com",
    )

    user = result.user

    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_staff_account_rejects_duplicate_username():
    user_factory(username="duplicate@example.com")

    with pytest.raises(
        AccountCreationError,
        match="An account with this email already exists.",
    ):
        create_restricted_staff_account(
            email=" duplicate@example.com ",
            password="safe-password",
        )


@pytest.mark.django_db
def test_create_customer_account_rejects_duplicate_email(customer):
    user_factory(username="duplicate@example.com", email="duplicate@example.com")

    with pytest.raises(
        AccountCreationError,
        match="An account with this email already exists.",
    ):
        create_customer_account(
            email=" DUPLICATE@EXAMPLE.COM ",
            customer=customer,
            password="safe-password",
        )


@pytest.mark.django_db
def test_create_account_rejects_empty_email():
    with pytest.raises(
        AccountCreationError,
        match="Account email must not be empty.",
    ):
        create_restricted_staff_account(
            email="   ",
            password="safe-password",
        )


@pytest.mark.django_db
def test_create_customer_account_allows_customer_contact_email(customer):
    result = create_customer_account(
        email=customer.email,
        customer=customer,
        password="safe-password",
    )

    assert result.user.email == customer.email

    membership = CustomerMembership.objects.get(user=result.user)
    assert membership.customer == customer
