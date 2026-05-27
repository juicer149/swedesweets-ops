from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django import forms
from django.forms import BaseFormSet, formset_factory

from common.form_layout import set_form_field_layout
from customers.models import Customer
from orders.datatypes import OrderLineInput
from orders.models import Order, OrderLine
from orders.order_limits import (
    MAX_BOXES_PER_PRODUCT_PER_ORDER,
    is_unusually_large_order_line,
)
from orders.product_choices import build_product_choice_context
from products.models import Product
from products.units import quantity_to_boxes


DEFAULT_ORDER_LINE_COUNT = 1
MIN_ORDER_QUANTITY = Decimal("0.001")


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
        available_boxes_by_product_id: dict[int, int] | None = None,
        **kwargs,
    ) -> None:
        self.available_boxes_by_product_id = available_boxes_by_product_id or {}
        super().__init__(*args, **kwargs)

    def label_from_instance(self, product: Product) -> str:
        available_boxes = self.available_boxes_by_product_id.get(product.id)

        if available_boxes is None:
            return f"{product.code_label} · {product.display_name}"

        return (
            f"{product.code_label} · "
            f"{product.display_name} · "
            f"{product.weight_per_box} g · "
            f"{_boxes_label(available_boxes)}"
        )

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
        available_boxes = self.available_boxes_by_product_id.get(product.id, 0)

        option["attrs"].update(
            {
                "data-code": product.code_label,
                "data-brand": product.brand,
                "data-name": product.display_name,
                "data-weight": f"{product.weight_per_box} g / box",
                "data-available-boxes": str(available_boxes),
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
            "weight_per_box",
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
        choices=OrderLine.Unit.choices,
        initial=OrderLine.Unit.KG,
        label="Unit",
        error_messages={
            "invalid_choice": "Choose boxes, kg or grams.",
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
        available_boxes_by_product_id: dict[int, int] | None = None,
        **kwargs,
    ) -> None:
        self.available_boxes_by_product_id = available_boxes_by_product_id or {}

        super().__init__(*args, **kwargs)

        product_field = self.fields["product"]
        product_field.queryset = product_queryset or Product.objects.none()

        if isinstance(product_field, ProductChoiceField):
            product_field.available_boxes_by_product_id = (
                self.available_boxes_by_product_id
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
            unit = OrderLine.Unit.KG
            cleaned_data["unit"] = unit

        if product is None or quantity is None:
            return cleaned_data

        boxes = _quantity_to_boxes_for_form(
            product=product,
            quantity=quantity,
            unit=unit,
        )

        cleaned_data["quantity_in_boxes"] = boxes

        available_boxes = self.available_boxes_by_product_id.get(product.id)

        if (
            is_unusually_large_order_line(boxes=boxes)
            and not _is_stock_shortage(
                requested_boxes=boxes,
                available_boxes=available_boxes,
            )
        ):
            self.add_error(
                "quantity",
                (
                    "This line is unusually large. "
                    f"Maximum is {_boxes_label(MAX_BOXES_PER_PRODUCT_PER_ORDER)} "
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
                "available_boxes_by_product_id": (
                    self.product_choice_context.available_boxes_by_product_id
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

        requested_boxes_by_product_id: dict[int, int] = defaultdict(int)
        product_names_by_id: dict[int, str] = {}

        for form in self.order_line_forms:
            product = form.cleaned_data["product"]
            boxes = form.cleaned_data["quantity_in_boxes"]

            requested_boxes_by_product_id[product.id] += boxes
            product_names_by_id[product.id] = product.display_name

        for product_id, requested_boxes in requested_boxes_by_product_id.items():
            available_boxes = self.product_choice_context.available_boxes_by_product_id.get(
                product_id,
                0,
            )

            if requested_boxes > available_boxes:
                product_name = product_names_by_id[product_id]

                raise forms.ValidationError(
                    (
                        f"Only {_boxes_label(available_boxes)} available "
                        f"for {product_name}."
                    )
                )

            if is_unusually_large_order_line(boxes=requested_boxes):
                product_name = product_names_by_id[product_id]

                raise forms.ValidationError(
                    (
                        f"{product_name} is unusually large. "
                        f"Maximum is {_boxes_label(MAX_BOXES_PER_PRODUCT_PER_ORDER)} "
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
    formset: BaseOrderLineFormSet,
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


def _quantity_to_boxes_for_form(
    *,
    product: Product,
    quantity: Decimal,
    unit: str,
) -> int:
    try:
        return quantity_to_boxes(
            product=product,
            quantity=quantity,
            unit=unit,
        )
    except ValueError as error:
        raise forms.ValidationError(str(error)) from error


def _is_stock_shortage(
    *,
    requested_boxes: int,
    available_boxes: int | None,
) -> bool:
    if available_boxes is None:
        return False

    return requested_boxes > available_boxes


def _boxes_label(boxes: int) -> str:
    return "1 box" if boxes == 1 else f"{boxes} boxes"
