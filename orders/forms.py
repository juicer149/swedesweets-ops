from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils.translation import gettext as _

from common.form_layout import set_form_field_layout
from customers.models import Customer
from orders.datatypes import OrderLineInput
from orders.models import Order, OrderLine
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
    is_unusually_large_order_line,
)
from orders.product_choices import build_product_choice_context
from products.models import Product
from products.units import quantity_to_units


DEFAULT_ORDER_LINE_COUNT = 1
MIN_ORDER_QUANTITY = Decimal("0.001")

MAX_UNITS_PER_PRODUCT_PER_ORDER = MAX_QUANTITY_PER_PRODUCT_PER_ORDER


def _order_line_stock_unit_value() -> str:
    gram_based_values = {
        OrderLine.Unit.KG,
        OrderLine.Unit.GRAMS,
    }

    for value, _label in OrderLine.Unit.choices:
        if value not in gram_based_values:
            return value

    return OrderLine.Unit.KG


def _order_line_unit_choices() -> tuple[tuple[str, str], ...]:
    stock_unit_value = _order_line_stock_unit_value()

    return tuple(
        (
            value,
            "Quantity" if value == stock_unit_value else label,
        )
        for value, label in OrderLine.Unit.choices
    )


ORDER_LINE_STOCK_UNIT_VALUE = _order_line_stock_unit_value()
ORDER_LINE_UNIT_CHOICES = _order_line_unit_choices()


class CustomerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, customer: Customer) -> str:
        city = getattr(customer, "city", "")

        if city:
            return f"{customer.name} — {city}"

        return customer.name


class ProductChoiceField(forms.ModelChoiceField):
    def __init__(
        self,
        *args,
        available_units_by_product_id: dict[int, int] | None = None,
        **kwargs,
    ) -> None:
        self.available_units_by_product_id = available_units_by_product_id or {}
        super().__init__(*args, **kwargs)

    def label_from_instance(self, product: Product) -> str:
        available_units = self.available_units_by_product_id.get(product.id)

        if available_units is None:
            return f"{product.code_label} · {product.display_name}"

        return _("%(product_label)s · %(available_quantity)s left") % {
            "product_label": (
                f"{product.code_label} · "
                f"{product.display_name} · "
                f"{product.unit_weight_label}"
            ),
            "available_quantity": available_units,
        }

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name=name,
            value=value,
            label=label,
            selected=selected,
            index=index,
            subindex=subindex,
            attrs=attrs,
        )

        if not value:
            return option

        product = value.instance
        available_units = self.available_units_by_product_id.get(product.id, 0)

        option["attrs"].update(
            {
                "data-code": product.code_label,
                "data-brand": product.brand,
                "data-name": product.display_name,
                "data-weight": product.unit_weight_label,
                "data-available-units": str(available_units),
                "data-available-quantity": str(available_units),
                "search": (
                    f"{product.code_label} "
                    f"{product.internal_number or ''} "
                    f"{product.brand} "
                    f"{product.name} "
                    f"{product.display_name} "
                    f"{product.sku}"
                ),
            }
        )

        return option


class OrderCreateForm(forms.Form):
    customer = CustomerChoiceField(
        queryset=Customer.objects.order_by("name"),
        label="Customer",
        empty_label="Choose customer",
        error_messages={
            "required": "Choose a customer.",
            "invalid_choice": "Choose a valid customer.",
        },
        widget=forms.Select(
            attrs={
                "data-enhanced-select": "true",
                "data-enhanced-select-search": "true",
            }
        ),
    )


class OrderLineForm(forms.Form):
    product = ProductChoiceField(
        queryset=Product.objects.filter(active=True).order_by(
            "internal_number",
            "brand",
            "name",
            "weight_per_unit",
        ),
        required=False,
        label="Product",
        empty_label="Choose product",
        error_messages={
            "invalid_choice": "Choose a valid available product.",
        },
        widget=forms.Select(
            attrs={
                "data-enhanced-select": "true",
                "data-enhanced-select-search": "true",
            }
        ),
    )

    unit = forms.ChoiceField(
        required=False,
        choices=ORDER_LINE_UNIT_CHOICES,
        initial=ORDER_LINE_STOCK_UNIT_VALUE,
        label="Unit",
        error_messages={
            "invalid_choice": "Choose quantity, kg, or grams.",
        },
        widget=forms.RadioSelect(
            attrs={
                "class": "radio-chip-group",
            }
        ),
    )

    quantity = forms.DecimalField(
        required=False,
        min_value=MIN_ORDER_QUANTITY,
        max_digits=12,
        decimal_places=3,
        label="Quantity",
        error_messages={
            "invalid": "Enter quantity using numbers only, e.g. 12 or 2.5.",
            "min_value": "Quantity must be greater than 0.",
            "max_digits": "Quantity is too large.",
            "max_decimal_places": "Use at most 3 decimal places.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. 2.5",
                "inputmode": "decimal",
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
            half=("unit", "quantity"),
        )

    def clean(self) -> dict:
        cleaned_data = super().clean()

        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")
        unit = cleaned_data.get("unit")

        if not product and quantity is None:
            return cleaned_data

        if product is None:
            self.add_error("product", "Choose a product for this line.")

        if quantity is None:
            self.add_error("quantity", "Enter a quantity for this line.")

        if not unit:
            unit = ORDER_LINE_STOCK_UNIT_VALUE
            cleaned_data["unit"] = unit

        if product is None or quantity is None:
            return cleaned_data

        quantity_in_units = _quantity_to_units_for_form(
            product=product,
            quantity=quantity,
            unit=unit,
        )

        cleaned_data["quantity_in_units"] = quantity_in_units

        available_units = self.available_units_by_product_id.get(product.id)

        if (
            is_unusually_large_order_line(quantity=quantity_in_units)
            and not _is_stock_shortage(
                requested_quantity=quantity_in_units,
                available_quantity=available_units,
            )
        ):
            self.add_error(
                "quantity",
                (
                    "This line is unusually large. "
                    f"Maximum is {product.stock_quantity_label(MAX_QUANTITY_PER_PRODUCT_PER_ORDER)} "
                    "per product."
                ),
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
        return OrderLineInput(
            product=self.cleaned_data["product"],
            quantity=self.cleaned_data["quantity"],
            unit=self.cleaned_data["unit"],
        )


class BaseOrderLineFormSet(BaseFormSet):
    def __init__(
        self,
        *args,
        order: Order | None = None,
        **kwargs,
    ) -> None:
        self.order = order
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
            }
        )

        return kwargs

    def clean(self) -> None:
        super().clean()

        if any(form.errors for form in self.forms):
            return

        if not self.order_line_forms:
            raise forms.ValidationError("Add at least one order line.")

        requested_quantity_by_product_id: dict[int, int] = defaultdict(int)
        product_names_by_id: dict[int, str] = {}
        products_by_id: dict[int, Product] = {}

        for form in self.order_line_forms:
            product = form.cleaned_data["product"]
            quantity = form.cleaned_data["quantity_in_units"]

            requested_quantity_by_product_id[product.id] += quantity
            product_names_by_id[product.id] = product.display_name
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
                product_name = product_names_by_id[product_id]

                raise forms.ValidationError(
                    (
                        f"Only {product.stock_quantity_label(available_quantity)} "
                        f"available for {product_name}."
                    )
                )

            if is_unusually_large_order_line(quantity=requested_quantity):
                product_name = product_names_by_id[product_id]

                raise forms.ValidationError(
                    (
                        f"{product_name} is unusually large. "
                        f"Maximum is {product.stock_quantity_label(MAX_QUANTITY_PER_PRODUCT_PER_ORDER)} "
                        "per order."
                    )
                )

    @property
    def order_line_forms(self) -> list[OrderLineForm]:
        return [
            form
            for form in self.forms
            if form.has_line_data
        ]


OrderLineFormSet = formset_factory(
    OrderLineForm,
    formset=BaseOrderLineFormSet,
    extra=DEFAULT_ORDER_LINE_COUNT,
)


class OrderCancelForm(forms.Form):
    reason = forms.ChoiceField(
        choices=Order.CancelReason.choices,
        label="Cancellation reason",
        error_messages={
            "required": "Choose a cancellation reason.",
            "invalid_choice": "Choose a valid cancellation reason.",
        },
    )

    note = forms.CharField(
        required=False,
        label="Cancellation note",
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Optional: add a short note.",
            }
        ),
    )


def build_order_line_inputs(
    formset: BaseFormSet,
) -> list[OrderLineInput]:
    return [
        form.to_order_line_input()
        for form in formset.order_line_forms
    ]


def build_order_line_initial_data(order: Order) -> list[dict[str, object]]:
    return [
        {
            "product": line.product_id,
            "unit": line.unit,
            "quantity": line.quantity,
        }
        for line in order.lines.select_related("product").order_by("id")
    ]


def _quantity_to_units_for_form(
    *,
    product: Product,
    quantity: Decimal,
    unit: str,
) -> int:
    try:
        return quantity_to_units(
            product=product,
            quantity=quantity,
            unit=unit,
        )
    except ValueError as error:
        raise forms.ValidationError(str(error)) from error


def _is_stock_shortage(
    *,
    requested_quantity: int,
    available_quantity: int | None,
) -> bool:
    if available_quantity is None:
        return False

    return requested_quantity > available_quantity
