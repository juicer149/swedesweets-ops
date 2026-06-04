from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from accounts.errors import InvalidAccountIdentity
from accounts.models import CustomerMembership, StaffAccount
from accounts.roles import StaffAccessLevel
from customers.models import Customer


User = get_user_model()


class AccountCreationError(ValueError):
    """Raised when an account cannot be created."""


@dataclass(frozen=True, slots=True)
class CreatedAccount:
    user: object
    temporary_password: str | None = None


def create_full_staff_account(
    *,
    email: str,
    password: str | None = None,
) -> CreatedAccount:
    return _create_staff_account(
        email=email,
        password=password,
        access_level=StaffAccessLevel.FULL,
    )


def create_restricted_staff_account(
    *,
    email: str,
    password: str | None = None,
) -> CreatedAccount:
    return _create_staff_account(
        email=email,
        password=password,
        access_level=StaffAccessLevel.RESTRICTED,
    )


@transaction.atomic
def create_customer_account(
    *,
    email: str,
    customer: Customer,
    password: str | None = None,
) -> CreatedAccount:
    user = _create_user_for_account(
        email=email,
        password=password,
    )

    try:
        CustomerMembership.objects.create(
            user=user,
            customer=customer,
        )
    except IntegrityError as error:
        raise AccountCreationError(
            "Could not create customer account."
        ) from error

    return CreatedAccount(user=user)


@transaction.atomic
def _create_staff_account(
    *,
    email: str,
    password: str | None,
    access_level: StaffAccessLevel,
) -> CreatedAccount:
    user = _create_user_for_account(
        email=email,
        password=password,
    )

    try:
        StaffAccount.objects.create(
            user=user,
            access_level=access_level,
        )
    except IntegrityError as error:
        raise AccountCreationError(
            "Could not create staff account."
        ) from error

    return CreatedAccount(user=user)


def _create_user_for_account(
    *,
    email: str,
    password: str | None,
):
    email = _normalize_email(email)

    if User.objects.filter(username=email).exists():
        raise AccountCreationError("An account with this email already exists.")

    if User.objects.filter(email=email).exists():
        raise AccountCreationError("An account with this email already exists.")

    user = User(
        username=email,
        email=email,
    )

    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()

    user.save()

    return user


def _normalize_email(value: str) -> str:
    email = value.strip().lower()

    if not email:
        raise AccountCreationError("Account email must not be empty.")

    return email
