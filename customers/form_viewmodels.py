from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from customers.forms import CustomerForm
from customers.models import Customer


@dataclass(frozen=True, slots=True)
class FormContextItem:
    label: str
    value: Any


@dataclass(frozen=True, slots=True)
class CustomerFormContext:
    form: CustomerForm
    title: str
    description: str
    submit_label: str
    cancel_url: str
    customer: Customer | None = None
    customer_context_items: list[FormContextItem] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "form": self.form,
            "customer": self.customer,
            "customer_context_items": self.customer_context_items or [],
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
        }


def build_create_customer_form_context(
    *,
    form: CustomerForm,
) -> CustomerFormContext:
    return CustomerFormContext(
        form=form,
        title="Add customer",
        description="",
        submit_label="Add customer",
        cancel_url=reverse("customers:index"),
    )


def build_edit_customer_form_context(
    *,
    form: CustomerForm,
    customer: Customer,
) -> CustomerFormContext:
    return CustomerFormContext(
        form=form,
        customer=customer,
        customer_context_items=build_customer_context_items(customer),
        title=f"Edit - {customer.name}",
        description="",
        submit_label="Update customer",
        cancel_url=reverse("customers:detail", kwargs={"customer_pk": customer.pk}),
    )


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
