"""
Customer application services.

These functions coordinate customer use-cases. Customer data belongs to the
customers domain. Orders may reference customers, but should not own customer
creation or customer validation rules.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from customers.errors import InvalidCustomerData
from customers.models import Customer, normalize_customer_email


@transaction.atomic
def create_customer(
    *,
    name: str,
    email: str,
    phone_number: str,
    country: str,
    city: str,
    address_line: str,
    user=None,
) -> Customer:
    """Create a customer with unique normalized email."""

    normalized_email = normalize_customer_email(email)

    if Customer.objects.filter(email=normalized_email).exists():
        raise InvalidCustomerData(
            f"Customer with email {normalized_email} already exists"
        )

    try:
        customer = Customer.objects.create(
            name=name,
            email=normalized_email,
            phone_number=phone_number,
            country=country,
            city=city,
            address_line=address_line,
        )
    except IntegrityError as exc:
        raise InvalidCustomerData(
            f"Customer with email {normalized_email} already exists"
        ) from exc

    customer.mark_as_created(user=user)

    return customer


@transaction.atomic
def update_customer(
    *,
    customer: Customer,
    name: str,
    email: str,
    phone_number: str,
    country: str,
    city: str,
    address_line: str,
    user=None,
) -> Customer:
    """Update editable customer contact and delivery data."""

    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    normalized_email = normalize_customer_email(email)

    email_is_taken = (
        Customer.objects
        .filter(email=normalized_email)
        .exclude(pk=customer.pk)
        .exists()
    )

    if email_is_taken:
        raise InvalidCustomerData(
            f"Customer with email {normalized_email} already exists"
        )

    customer.name = name
    customer.email = normalized_email
    customer.phone_number = phone_number
    customer.country = country
    customer.city = city
    customer.address_line = address_line

    try:
        customer.save(
            update_fields=[
                "name",
                "email",
                "phone_number",
                "country",
                "city",
                "address_line",
            ]
        )
    except IntegrityError as exc:
        raise InvalidCustomerData(
            f"Customer with email {normalized_email} already exists"
        ) from exc

    customer.mark_as_edited(user=user)

    return customer


@transaction.atomic
def deactivate_customer(
    *,
    customer: Customer,
    user=None,
) -> Customer:
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    customer.deactivate(user=user)

    return customer


@transaction.atomic
def reactivate_customer(
    *,
    customer: Customer,
    user=None,
) -> Customer:
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    customer.reactivate(user=user)

    return customer
