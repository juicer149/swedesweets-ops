from __future__ import annotations

from customers.models import Customer
from customers.services import create_customer


def customer_factory(
    *,
    name: str = "Nordic Corner Shop",
    email: str = "orders@example.fr",
    phone_number: str = "+33 6 12 34 56 78",
    country: str = "FR",
    city: str = "Chamonix-Mont-Blanc",
    address_line: str = "123 Rue du Mont Blanc",
) -> Customer:
    return create_customer(
        name=name,
        email=email,
        phone_number=phone_number,
        country=country,
        city=city,
        address_line=address_line,
    )
