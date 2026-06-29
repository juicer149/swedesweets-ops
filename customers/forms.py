from __future__ import annotations

from django import forms

from common.form_layout import set_form_field_layout
from customers.models import (
    CUSTOMER_COUNTRY_LABELS,
    MAX_CUSTOMER_ADDRESS_LINE_LENGTH,
    MAX_CUSTOMER_CITY_LENGTH,
    MAX_CUSTOMER_NAME_LENGTH,
    MAX_CUSTOMER_PHONE_LENGTH,
    Customer,
)

CUSTOMER_COUNTRY_CHOICES = list(CUSTOMER_COUNTRY_LABELS.items())


class CustomerForm(forms.Form):
    name = forms.CharField(
        max_length=MAX_CUSTOMER_NAME_LENGTH,
        label="Customer name",
        error_messages={
            "required": "Enter the customer name.",
            "max_length": (
                f"Customer name must be at most {MAX_CUSTOMER_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Nordic Corner Shop",
                "autocomplete": "name",
            }
        ),
    )

    email = forms.EmailField(
        max_length=254,
        label="Email",
        error_messages={
            "required": "Enter an email address.",
            "invalid": "Enter a valid email address.",
            "max_length": "Email address must be at most 254 characters.",
        },
        widget=forms.EmailInput(
            attrs={
                "placeholder": "e.g. orders@example.fr",
                "autocomplete": "email",
            }
        ),
    )

    phone_number = forms.CharField(
        max_length=MAX_CUSTOMER_PHONE_LENGTH,
        label="Phone number",
        error_messages={
            "required": "Enter a phone number.",
            "max_length": (
                f"Phone number must be at most {MAX_CUSTOMER_PHONE_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. +33 6 12 34 56 78",
                "autocomplete": "tel",
            }
        ),
    )

    country = forms.ChoiceField(
        choices=CUSTOMER_COUNTRY_CHOICES,
        label="Country",
        initial="FR",
        error_messages={
            "required": "Choose a country.",
            "invalid_choice": "Choose a valid country.",
        },
        widget=forms.Select(
            attrs={
                "autocomplete": "country",
                "data-enhanced-select": "true",
                "data-enhanced-select-search": "false",
            }
        ),
    )

    city = forms.CharField(
        max_length=MAX_CUSTOMER_CITY_LENGTH,
        label="City",
        initial="Chamonix-Mont-Blanc",
        error_messages={
            "required": "Enter a city.",
            "max_length": (
                f"City must be at most {MAX_CUSTOMER_CITY_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Chamonix-Mont-Blanc",
                "autocomplete": "address-level2",
            }
        ),
    )

    address_line = forms.CharField(
        max_length=MAX_CUSTOMER_ADDRESS_LINE_LENGTH,
        label="Address",
        error_messages={
            "required": "Enter a street address.",
            "max_length": (
                f"Address must be at most "
                f"{MAX_CUSTOMER_ADDRESS_LINE_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. 123 Rue du Mont Blanc",
                "autocomplete": "street-address",
            }
        ),
    )

    def __init__(self, *args, customer: Customer | None = None, **kwargs) -> None:
        self.customer = customer
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            full=("name", "address_line"),
            half=("email", "phone_number", "country", "city"),
        )


def build_customer_edit_initial_data(customer: Customer) -> dict[str, object]:
    return {
        "name": customer.name,
        "email": customer.email,
        "phone_number": customer.phone_number,
        "country": customer.country,
        "city": customer.city,
        "address_line": customer.address_line,
    }
