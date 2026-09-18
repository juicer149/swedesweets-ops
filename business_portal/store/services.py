from __future__ import annotations

from customers.models import Customer
from customers.services import update_customer


def update_portal_customer_profile(
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
    """Update the current portal customer's editable store profile."""

    return update_customer(
        customer=customer,
        name=name,
        email=email,
        phone_number=phone_number,
        country=country,
        city=city,
        address_line=address_line,
        user=user,
    )
