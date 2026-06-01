from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from customers.models import Customer


@dataclass(frozen=True)
class FormContextItem:
    label: str
    value: Any


def build_customer_context_items(customer: Customer) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="Email",
            value=customer.email,
        ),
        FormContextItem(
            label="Phone",
            value=customer.phone_number,
        ),
        FormContextItem(
            label="City",
            value=customer.city,
        ),
    ]
