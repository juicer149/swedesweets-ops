from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from accounts.errors import AccountCreationError
from accounts.models import CustomerMembership, StaffAccount
from accounts.roles import StaffAccessLevel
from customers.models import Customer


User = get_user_model()


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


def create_internal_account(
    *,
    email: str,
    access_level: str | StaffAccessLevel,
    password: str | None = None,
) -> CreatedAccount:
    try:
        normalized_access_level = StaffAccessLevel(access_level)
    except ValueError as error:
        raise AccountCreationError("Choose a valid staff access level.") from error

    return _create_staff_account(
        email=email,
        password=password,
        access_level=normalized_access_level,
    )


@transaction.atomic
def update_internal_account(
    *,
    user,
    email: str,
    first_name: str,
    last_name: str,
    access_level: str | StaffAccessLevel,
    is_active: bool,
    actor,
):
    try:
        normalized_access_level = StaffAccessLevel(access_level)
    except ValueError as error:
        raise AccountCreationError("Choose a valid staff access level.") from error

    email = _normalize_email(email)

    staff_account = StaffAccount.objects.select_for_update().get(user=user)
    user = User.objects.select_for_update().get(pk=user.pk)

    _validate_internal_account_update(
        user=user,
        staff_account=staff_account,
        email=email,
        access_level=normalized_access_level,
        is_active=is_active,
        actor=actor,
    )

    user.username = email
    user.email = email
    user.first_name = first_name.strip()
    user.last_name = last_name.strip()
    user.is_active = is_active

    staff_account.access_level = normalized_access_level

    try:
        user.save(
            update_fields=[
                "username",
                "email",
                "first_name",
                "last_name",
                "is_active",
            ]
        )
        staff_account.save(update_fields=["access_level"])
    except IntegrityError as error:
        raise AccountCreationError(
            "An account with this email already exists."
        ) from error

    return user


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
def set_customer_account_active_status(
    *,
    user,
    is_active: bool,
    actor,
):
    if user.pk == actor.pk and not is_active:
        raise AccountCreationError("You cannot deactivate your own account.")

    membership_exists = (
        CustomerMembership.objects
        .select_for_update()
        .filter(user=user)
        .exists()
    )

    if not membership_exists:
        raise AccountCreationError("This is not a customer account.")

    user = User.objects.select_for_update().get(pk=user.pk)
    user.is_active = is_active
    user.save(update_fields=["is_active"])

    return user


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

    # TODO: Replace manually assigned temporary passwords with an emailed
    # password setup flow. This helper already supports password=None, which
    # creates an unusable password until the user sets one through a tokenized
    # setup/reset link.
    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()

    try:
        user.save()
    except IntegrityError as error:
        raise AccountCreationError(
            "An account with this email already exists."
        ) from error

    return user


def _validate_internal_account_update(
    *,
    user,
    staff_account: StaffAccount,
    email: str,
    access_level: StaffAccessLevel,
    is_active: bool,
    actor,
) -> None:
    if User.objects.filter(username=email).exclude(pk=user.pk).exists():
        raise AccountCreationError("An account with this email already exists.")

    if User.objects.filter(email=email).exclude(pk=user.pk).exists():
        raise AccountCreationError("An account with this email already exists.")

    if user.pk == actor.pk and not is_active:
        raise AccountCreationError("You cannot deactivate your own account.")

    if (
        user.pk == actor.pk
        and staff_account.access_level == StaffAccessLevel.FULL
        and access_level == StaffAccessLevel.RESTRICTED
    ):
        raise AccountCreationError(
            "You cannot remove your own account management access."
        )


def _normalize_email(value: str) -> str:
    email = value.strip().lower()

    if not email:
        raise AccountCreationError("Account email must not be empty.")

    return email
