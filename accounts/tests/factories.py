from __future__ import annotations

from django.contrib.auth import get_user_model

from accounts.models import CustomerMembership, StaffAccount
from accounts.roles import StaffAccessLevel
from customers.models import Customer

User = get_user_model()


def user_factory(
    *,
    username: str = "user@example.com",
    email: str | None = None,
    password: str = "password",
):
    return User.objects.create_user(
        username=username,
        email=email or username,
        password=password,
    )


def superuser_factory(
    *,
    username: str = "owner@example.com",
    email: str | None = None,
    password: str = "password",
):
    return User.objects.create_superuser(
        username=username,
        email=email or username,
        password=password,
    )


def staff_account_factory(
    *,
    user=None,
    access_level: StaffAccessLevel = StaffAccessLevel.RESTRICTED,
) -> StaffAccount:
    if user is None:
        user = user_factory()

    return StaffAccount.objects.create(
        user=user,
        access_level=access_level,
    )


def full_staff_user_factory(
    *,
    username: str = "full-staff@example.com",
):
    user = user_factory(username=username)
    staff_account_factory(
        user=user,
        access_level=StaffAccessLevel.FULL,
    )
    return user


def restricted_staff_user_factory(
    *,
    username: str = "restricted-staff@example.com",
):
    user = user_factory(username=username)
    staff_account_factory(
        user=user,
        access_level=StaffAccessLevel.RESTRICTED,
    )
    return user


def customer_membership_factory(
    *,
    user=None,
    customer: Customer,
) -> CustomerMembership:
    if user is None:
        user = user_factory()

    return CustomerMembership.objects.create(
        user=user,
        customer=customer,
    )


def customer_user_factory(
    *,
    customer: Customer,
    username: str = "customer@example.com",
):
    user = user_factory(username=username)
    customer_membership_factory(
        user=user,
        customer=customer,
    )
    return user
