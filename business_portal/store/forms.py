from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy

from common.form_layout import set_form_field_layout
from customers.models import (
    CUSTOMER_COUNTRY_LABELS,
    MAX_CUSTOMER_ADDRESS_LINE_LENGTH,
    MAX_CUSTOMER_CITY_LENGTH,
    MAX_CUSTOMER_NAME_LENGTH,
    MAX_CUSTOMER_PHONE_LENGTH,
    Customer,
)


PORTAL_CUSTOMER_COUNTRY_CHOICES = list(
    CUSTOMER_COUNTRY_LABELS.items()
)


class CustomerProfileForm(forms.Form):
    name = forms.CharField(
        max_length=MAX_CUSTOMER_NAME_LENGTH,
        label=gettext_lazy("Store name"),
        error_messages={
            "required": gettext_lazy(
                "Enter the store name."
            ),
            "max_length": gettext_lazy(
                "Store name is too long."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "organization",
            }
        ),
    )

    email = forms.EmailField(
        max_length=254,
        label=gettext_lazy("Email"),
        error_messages={
            "required": gettext_lazy(
                "Enter an email address."
            ),
            "invalid": gettext_lazy(
                "Enter a valid email address."
            ),
            "max_length": gettext_lazy(
                "Email address is too long."
            ),
        },
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
            }
        ),
    )

    phone_number = forms.CharField(
        max_length=MAX_CUSTOMER_PHONE_LENGTH,
        label=gettext_lazy("Phone number"),
        error_messages={
            "required": gettext_lazy(
                "Enter a phone number."
            ),
            "max_length": gettext_lazy(
                "Phone number is too long."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "tel",
            }
        ),
    )

    country = forms.ChoiceField(
        choices=PORTAL_CUSTOMER_COUNTRY_CHOICES,
        label=gettext_lazy("Country"),
        error_messages={
            "required": gettext_lazy(
                "Choose a country."
            ),
            "invalid_choice": gettext_lazy(
                "Choose a valid country."
            ),
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
        label=gettext_lazy("City"),
        error_messages={
            "required": gettext_lazy(
                "Enter a city."
            ),
            "max_length": gettext_lazy(
                "City is too long."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "address-level2",
            }
        ),
    )

    address_line = forms.CharField(
        max_length=MAX_CUSTOMER_ADDRESS_LINE_LENGTH,
        label=gettext_lazy("Address"),
        error_messages={
            "required": gettext_lazy(
                "Enter a street address."
            ),
            "max_length": gettext_lazy(
                "Address is too long."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "street-address",
            }
        ),
    )

    def __init__(
        self,
        *args,
        customer: Customer,
        **kwargs,
    ) -> None:
        self.customer = customer
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            full=(
                "name",
                "address_line",
            ),
            half=(
                "email",
                "phone_number",
                "country",
                "city",
            ),
        )


def build_customer_profile_initial_data(
    customer: Customer,
) -> dict[str, object]:
    return {
        "name": customer.name,
        "email": customer.email,
        "phone_number": customer.phone_number,
        "country": customer.country,
        "city": customer.city,
        "address_line": customer.address_line,
    }
