from __future__ import annotations

from collections import defaultdict
from typing import Any

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils.translation import gettext as _
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
from orders.datatypes import OrderLineInput
from orders.forms import ProductChoiceField
from orders.models import Order
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
    is_unusually_large_order_line,
)
from orders.product_choices import build_product_choice_context
from products.models import Product
from products.presentation import translated_product_name

DEFAULT_PORTAL_ORDER_LINE_COUNT = 1
MIN_PORTAL_ORDER_QUANTITY = 1


class PortalOrderLineForm(forms.Form):
    product = ProductChoiceField(
        queryset=Product.objects.none(),
        required=False,
        label=gettext_lazy("Product"),
        empty_label=gettext_lazy("Choose product"),
        error_messages={
            "invalid_choice": gettext_lazy("Choose a valid available product."),
        },
        widget=forms.Select(
            attrs={
                "data-enhanced-select": "true",
                "data-enhanced-select-search": "true",
            }
        ),
    )

    quantity = forms.IntegerField(
        required=False,
        min_value=MIN_PORTAL_ORDER_QUANTITY,
        max_value=MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
        label=gettext_lazy("Quantity"),
        error_messages={
            "invalid": gettext_lazy("Enter a whole number of units."),
            "min_value": gettext_lazy("Quantity must be at least 1."),
            "max_value": gettext_lazy("Quantity is too large."),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": gettext_lazy("e.g. 2"),
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(
        self,
        *args,
        product_queryset=None,
        available_units_by_product_id: dict[int, int] | None = None,
        language_code: str | None = None,
        **kwargs,
    ) -> None:
        self.available_units_by_product_id = available_units_by_product_id or {}
        self.language_code = language_code

        super().__init__(*args, **kwargs)

        product_field = self.fields["product"]
        product_field.queryset = product_queryset or Product.objects.none()

        if isinstance(product_field, ProductChoiceField):
            product_field.available_units_by_product_id = (
                self.available_units_by_product_id
            )
            product_field.language_code = self.language_code
            product_field.show_available_units = False

        set_form_field_layout(
            self,
            half=(
                "product",
                "quantity",
            ),
        )

        self.fields["quantity"].layout_class = "form-field--portal-order-quantity"

    def clean(self) -> dict:
        cleaned_data = super().clean()

        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")

        if product is None and quantity is None:
            return cleaned_data

        if product is None:
            self.add_error(
                "product",
                _("Choose a product for this line."),
            )

        if quantity is None:
            self.add_error(
                "quantity",
                _("Enter a quantity for this line."),
            )

        return cleaned_data

    @property
    def has_line_data(self) -> bool:
        if not hasattr(self, "cleaned_data"):
            return False

        return bool(
            self.cleaned_data.get("product")
            or self.cleaned_data.get("quantity") is not None
        )

    def to_order_line_input(self) -> OrderLineInput:
        return OrderLineInput.units(
            product=self.cleaned_data["product"],
            quantity=self.cleaned_data["quantity"],
        )


class BasePortalOrderLineFormSet(BaseFormSet):
    def __init__(
        self,
        *args,
        order: Order | None = None,
        require_lines: bool = True,
        language_code: str | None = None,
        **kwargs,
    ) -> None:
        self.order = order
        self.require_lines = require_lines
        self.language_code = language_code
        self.product_choice_context = build_product_choice_context(order=order)
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index: int | None) -> dict[str, Any]:
        kwargs = super().get_form_kwargs(index)

        kwargs.update(
            {
                "product_queryset": self.product_choice_context.queryset,
                "available_units_by_product_id": (
                    self.product_choice_context.available_units_by_product_id
                ),
                "language_code": self.language_code,
            }
        )

        return kwargs

    def clean(self) -> None:
        super().clean()

        if any(form.errors for form in self.forms):
            return

        if not self.order_line_forms:
            if self.require_lines:
                raise forms.ValidationError(
                    _("Add at least one product."),
                )

            return

        requested_quantity_by_product_id: dict[int, int] = defaultdict(int)
        products_by_id: dict[int, Product] = {}

        for form in self.order_line_forms:
            product = form.cleaned_data["product"]
            quantity = form.cleaned_data["quantity"]

            requested_quantity_by_product_id[product.id] += quantity
            products_by_id[product.id] = product

        for product_id, requested_quantity in requested_quantity_by_product_id.items():
            available_quantity = (
                self.product_choice_context.available_units_by_product_id.get(
                    product_id,
                    0,
                )
            )
            product = products_by_id[product_id]

            if requested_quantity > available_quantity:
                raise forms.ValidationError(
                    _("Only %(available)s available for %(product)s.")
                    % {
                        "available": product.stock_quantity_label(available_quantity),
                        "product": _portal_product_name(
                            product, language_code=self.language_code
                        ),
                    }
                )

            if is_unusually_large_order_line(quantity=requested_quantity):
                raise forms.ValidationError(
                    _(
                        "%(product)s is unusually large. "
                        "Maximum is %(maximum)s per order."
                    )
                    % {
                        "product": _portal_product_name(
                            product, language_code=self.language_code
                        ),
                        "maximum": product.stock_quantity_label(
                            MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                        ),
                    }
                )

    @property
    def order_line_forms(self) -> list[PortalOrderLineForm]:
        return [form for form in self.forms if form.has_line_data]


PortalOrderLineFormSet = formset_factory(
    PortalOrderLineForm,
    formset=BasePortalOrderLineFormSet,
    extra=DEFAULT_PORTAL_ORDER_LINE_COUNT,
)


def build_portal_order_line_inputs(
    formset: BasePortalOrderLineFormSet,
) -> list[OrderLineInput]:
    return [form.to_order_line_input() for form in formset.order_line_forms]


PORTAL_CUSTOMER_COUNTRY_CHOICES = list(CUSTOMER_COUNTRY_LABELS.items())


class CustomerProfileForm(forms.Form):
    name = forms.CharField(
        max_length=MAX_CUSTOMER_NAME_LENGTH,
        label=gettext_lazy("Store name"),
        error_messages={
            "required": gettext_lazy("Enter the store name."),
            "max_length": gettext_lazy("Store name is too long."),
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
            "required": gettext_lazy("Enter an email address."),
            "invalid": gettext_lazy("Enter a valid email address."),
            "max_length": gettext_lazy("Email address is too long."),
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
            "required": gettext_lazy("Enter a phone number."),
            "max_length": gettext_lazy("Phone number is too long."),
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
            "required": gettext_lazy("Choose a country."),
            "invalid_choice": gettext_lazy("Choose a valid country."),
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
            "required": gettext_lazy("Enter a city."),
            "max_length": gettext_lazy("City is too long."),
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
            "required": gettext_lazy("Enter a street address."),
            "max_length": gettext_lazy("Address is too long."),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "street-address",
            }
        ),
    )

    def __init__(self, *args, customer: Customer, **kwargs) -> None:
        self.customer = customer
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            full=("name", "address_line"),
            half=("email", "phone_number", "country", "city"),
        )


def build_customer_profile_initial_data(customer: Customer) -> dict[str, object]:
    return {
        "name": customer.name,
        "email": customer.email,
        "phone_number": customer.phone_number,
        "country": customer.country,
        "city": customer.city,
        "address_line": customer.address_line,
    }


def build_portal_order_line_initial_data(
    order: Order,
) -> list[dict[str, object]]:
    return [
        {
            "product": line.product_id,
            "quantity": line.quantity_in_units,
        }
        for line in order.lines.select_related("product").order_by("id")
    ]


def _portal_product_name(
    product: Product,
    *,
    language_code: str | None,
) -> str:
    if not language_code:
        return product.display_name

    return translated_product_name(
        product,
        language_code=language_code,
    )
