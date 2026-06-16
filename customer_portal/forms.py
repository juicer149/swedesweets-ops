from __future__ import annotations

from collections import defaultdict
from typing import Any

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from common.form_layout import set_form_field_layout
from orders.datatypes import OrderLineInput
from orders.forms import ProductChoiceField
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
    is_unusually_large_order_line,
)
from orders.product_choices import build_product_choice_context
from products.models import Product


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
        **kwargs,
    ) -> None:
        self.available_units_by_product_id = available_units_by_product_id or {}

        super().__init__(*args, **kwargs)

        product_field = self.fields["product"]
        product_field.queryset = product_queryset or Product.objects.none()

        if isinstance(product_field, ProductChoiceField):
            product_field.available_units_by_product_id = (
                self.available_units_by_product_id
            )

        set_form_field_layout(
            self,
            full=("product",),
            half=("quantity",),
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
        **kwargs,
    ) -> None:
        self.product_choice_context = build_product_choice_context()
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index: int | None) -> dict[str, Any]:
        kwargs = super().get_form_kwargs(index)

        kwargs.update(
            {
                "product_queryset": self.product_choice_context.queryset,
                "available_units_by_product_id": (
                    self.product_choice_context.available_units_by_product_id
                ),
            }
        )

        return kwargs

    def clean(self) -> None:
        super().clean()

        if any(form.errors for form in self.forms):
            return

        if not self.order_line_forms:
            raise forms.ValidationError(
                _("Add at least one product."),
            )

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
                    _("Only %(available)s available for %(product)s.") % {
                        "available": product.stock_quantity_label(
                            available_quantity
                        ),
                        "product": product.display_name,
                    }
                )

            if is_unusually_large_order_line(quantity=requested_quantity):
                raise forms.ValidationError(
                    _(
                        "%(product)s is unusually large. "
                        "Maximum is %(maximum)s per order."
                    ) % {
                        "product": product.display_name,
                        "maximum": product.stock_quantity_label(
                            MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                        ),
                    }
                )

    @property
    def order_line_forms(self) -> list[PortalOrderLineForm]:
        return [
            form
            for form in self.forms
            if form.has_line_data
        ]


PortalOrderLineFormSet = formset_factory(
    PortalOrderLineForm,
    formset=BasePortalOrderLineFormSet,
    extra=DEFAULT_PORTAL_ORDER_LINE_COUNT,
)


def build_portal_order_line_inputs(
    formset: BasePortalOrderLineFormSet,
) -> list[OrderLineInput]:
    return [
        form.to_order_line_input()
        for form in formset.order_line_forms
    ]
