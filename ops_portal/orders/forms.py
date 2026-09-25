from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils.translation import gettext as _

from business.datatypes import BusinessOfferLineInput
from business.offer_choices import build_business_offer_choice_context
from customers.models import Customer
from orders.models import Order, OrderLine
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
    is_unusually_large_order_line,
)
from pricing.models import CommercialPrice
from products.models import Product
from ops_portal.products.presentation import (
    translated_product_catalog_label,
    translated_product_name,
)
from products.units import quantity_to_units

# extra=0 below - lines are never pre-rendered blank; they only ever appear
# via order_lines.js in response to a selection in AddOrderLineProductForm.
DEFAULT_ORDER_LINE_COUNT = 0

# Kept at the original fractional precision - kg/gram remain valid domain
# input (unit is just never exposed as a frontend choice), so the field
# itself must still accept e.g. 12.5 kg. Only the rendered widget is forced
# to whole-number stepper behavior in OrderLineForm.__init__ below, since
# that is the only path the current UI actually drives.
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


class BusinessOfferChoiceField(forms.ModelChoiceField):
    def __init__(
        self,
        *args,
        available_units_by_offer_id: dict[int, int] | None = None,
        language_code: str | None = None,
        show_available_units: bool = True,
        **kwargs,
    ) -> None:
        self.available_units_by_offer_id = (
            available_units_by_offer_id or {}
        )
        self.language_code = language_code
        self.show_available_units = show_available_units
        super().__init__(*args, **kwargs)

    def label_from_instance(
        self,
        offer: CommercialPrice,
    ) -> str:
        available_units = (
            self.available_units_by_offer_id.get(
                offer.id
            )
        )
        offer_label = self._offer_label(
            offer
        )

        if (
            available_units is None
            or not self.show_available_units
        ):
            return offer_label

        return _(
            "%(offer_label)s · %(available_quantity)s left"
        ) % {
            "offer_label": offer_label,
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

        offer = value.instance
        product = offer.product

        option["attrs"].update(
            {
                "data-code": product.code_label,
                "data-brand": product.brand,
                "data-name": self._product_name(
                    product
                ),
                "data-weight": product.unit_weight_label,
                "data-offer-detail": _offer_detail(
                    offer
                ),
                "data-available-units": str(
                    self.available_units_by_offer_id.get(
                        offer.id,
                        0,
                    )
                ),
                "data-available-quantity": str(
                    self.available_units_by_offer_id.get(
                        offer.id,
                        0,
                    )
                ),
                "search": (
                    f"{product.code_label} "
                    f"{product.internal_number or ''} "
                    f"{product.brand} "
                    f"{product.name} "
                    f"{product.display_name} "
                    f"{self._product_name(product)} "
                    f"{self._product_label(product)} "
                    f"{product.sku} "
                    f"{_offer_detail(offer)}"
                ),
            }
        )

        return option

    def _offer_label(
        self,
        offer: CommercialPrice,
    ) -> str:
        product_label = self._product_label(
            offer.product
        )
        offer_detail = _offer_detail(
            offer
        )

        if not offer_detail:
            return product_label

        return (
            f"{product_label} · "
            f"{offer_detail}"
        )

    def _product_label(
        self,
        product: Product,
    ) -> str:
        if self.language_code:
            return translated_product_catalog_label(
                product,
                language_code=self.language_code,
            )

        return (
            f"{product.code_label} · "
            f"{product.display_name} · "
            f"{product.unit_weight_label}"
        )

    def _product_name(
        self,
        product: Product,
    ) -> str:
        if self.language_code:
            return translated_product_name(
                product,
                language_code=self.language_code,
            )

        return product.display_name


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


class AddOrderLineProductForm(forms.Form):
    """Standalone BUSINESS offer picker used to create formset lines.

    The selected value is a CommercialPrice id. The field is not itself
    submitted as an order line; order_lines.js copies the selected offer id
    into the hidden field of a newly created OrderLineForm.
    """

    commercial_offer = BusinessOfferChoiceField(
        queryset=CommercialPrice.objects.none(),
        required=False,
        label="Add product offer",
        empty_label="Choose a product offer to add",
        error_messages={
            "invalid_choice": "Choose a valid available offer.",
        },
        widget=forms.Select(
            attrs={
                "data-add-order-line-select": "true",
                "data-enhanced-select": "true",
                "data-enhanced-select-search": "true",
            }
        ),
    )

    def __init__(
        self,
        *args,
        offer_queryset=None,
        available_units_by_offer_id: dict[int, int] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        offer_field = self.fields["commercial_offer"]
        offer_field.queryset = (
            offer_queryset
            if offer_queryset is not None
            else CommercialPrice.objects.none()
        )
        offer_field.available_units_by_offer_id = (
            available_units_by_offer_id or {}
        )


class OrderLineForm(forms.Form):
    commercial_offer = BusinessOfferChoiceField(
        queryset=CommercialPrice.objects.none(),
        required=False,
        error_messages={
            "invalid_choice": "Choose a valid available offer.",
        },
        widget=forms.HiddenInput(
            attrs={
                "data-order-line-offer-input": "true",
            }
        ),
    )

    unit = forms.ChoiceField(
        required=False,
        choices=ORDER_LINE_UNIT_CHOICES,
        initial=ORDER_LINE_STOCK_UNIT_VALUE,
        error_messages={
            "invalid_choice": "Choose quantity, kg, or grams.",
        },
        widget=forms.HiddenInput(),
    )

    quantity = forms.DecimalField(
        required=False,
        min_value=MIN_ORDER_QUANTITY,
        max_digits=12,
        decimal_places=3,
        error_messages={
            "invalid": "Enter quantity using numbers only, e.g. 12 or 2.5.",
            "min_value": "Quantity must be greater than 0.",
            "max_digits": "Quantity is too large.",
            "max_decimal_places": "Use at most 3 decimal places.",
        },
        widget=forms.NumberInput(
            attrs={
                "class": "quantity-stepper__input",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-quantity-input": "true",
            }
        ),
    )

    def __init__(
        self,
        *args,
        offer_queryset=None,
        available_units_by_offer_id: dict[int, int] | None = None,
        **kwargs,
    ) -> None:
        self.available_units_by_offer_id = (
            available_units_by_offer_id or {}
        )

        super().__init__(*args, **kwargs)

        offer_field = self.fields["commercial_offer"]
        offer_field.queryset = (
            offer_queryset
            if offer_queryset is not None
            else CommercialPrice.objects.none()
        )

        if isinstance(
            offer_field,
            BusinessOfferChoiceField,
        ):
            offer_field.available_units_by_offer_id = (
                self.available_units_by_offer_id
            )

        self.fields["quantity"].widget.attrs["step"] = "1"
        self.fields["quantity"].widget.attrs["min"] = "1"

    def clean(self) -> dict:
        cleaned_data = super().clean()

        offer = cleaned_data.get(
            "commercial_offer"
        )
        quantity = cleaned_data.get(
            "quantity"
        )
        unit = cleaned_data.get(
            "unit"
        )

        if offer is None and quantity is None:
            return cleaned_data

        if offer is None:
            self.add_error(
                "commercial_offer",
                "Choose an offer for this line.",
            )

        if quantity is None:
            self.add_error(
                "quantity",
                "Enter a quantity for this line.",
            )

        if not unit:
            unit = ORDER_LINE_STOCK_UNIT_VALUE
            cleaned_data["unit"] = unit

        if offer is None or quantity is None:
            return cleaned_data

        product = offer.product

        quantity_in_units = _quantity_to_units_for_form(
            product=product,
            quantity=quantity,
            unit=unit,
        )

        cleaned_data[
            "quantity_in_units"
        ] = quantity_in_units

        available_units = (
            self.available_units_by_offer_id.get(
                offer.id
            )
        )

        if is_unusually_large_order_line(
            quantity=quantity_in_units
        ) and not _is_stock_shortage(
            requested_quantity=quantity_in_units,
            available_quantity=available_units,
        ):
            self.add_error(
                "quantity",
                (
                    "This line is unusually large. "
                    f"Maximum is "
                    f"{product.stock_quantity_label(MAX_QUANTITY_PER_PRODUCT_PER_ORDER)} "
                    "per product."
                ),
            )

        return cleaned_data

    @property
    def has_line_data(self) -> bool:
        if not hasattr(
            self,
            "cleaned_data",
        ):
            return False

        return bool(
            self.cleaned_data.get(
                "commercial_offer"
            )
            or self.cleaned_data.get(
                "quantity"
            ) is not None
        )

    def to_business_offer_line_input(
        self,
    ) -> BusinessOfferLineInput:
        offer = self.cleaned_data[
            "commercial_offer"
        ]

        return BusinessOfferLineInput(
            commercial_offer_id=offer.pk,
            quantity=self.cleaned_data[
                "quantity"
            ],
            unit=self.cleaned_data[
                "unit"
            ],
        )


class BaseOrderLineFormSet(BaseFormSet):
    def __init__(
        self,
        *args,
        order: Order | None = None,
        **kwargs,
    ) -> None:
        self.order = order
        self.offer_choice_context = (
            build_business_offer_choice_context(
                order=order,
            )
        )
        super().__init__(
            *args,
            **kwargs,
        )

    def get_form_kwargs(
        self,
        index: int | None,
    ) -> dict[str, Any]:
        kwargs = super().get_form_kwargs(
            index
        )

        kwargs.update(
            {
                "offer_queryset": (
                    self.offer_choice_context.queryset
                ),
                "available_units_by_offer_id": (
                    self.offer_choice_context
                    .available_units_by_offer_id
                ),
            }
        )

        return kwargs

    def clean(self) -> None:
        super().clean()

        if any(
            form.errors
            for form in self.forms
        ):
            return

        if not self.order_line_forms:
            raise forms.ValidationError(
                "Add at least one order line."
            )

        requested_quantity_by_offer_id: dict[
            int,
            int,
        ] = defaultdict(int)
        requested_quantity_by_product_id: dict[
            int,
            int,
        ] = defaultdict(int)
        offers_by_id: dict[
            int,
            CommercialPrice,
        ] = {}
        products_by_id: dict[
            int,
            Product,
        ] = {}

        for form in self.order_line_forms:
            offer = form.cleaned_data[
                "commercial_offer"
            ]
            quantity = form.cleaned_data[
                "quantity_in_units"
            ]
            product = offer.product

            requested_quantity_by_offer_id[
                offer.id
            ] += quantity
            requested_quantity_by_product_id[
                product.id
            ] += quantity

            offers_by_id[
                offer.id
            ] = offer
            products_by_id[
                product.id
            ] = product

        for (
            offer_id,
            requested_quantity,
        ) in requested_quantity_by_offer_id.items():
            available_quantity = (
                self.offer_choice_context
                .available_units_by_offer_id
                .get(
                    offer_id,
                    0,
                )
            )

            if (
                requested_quantity
                > available_quantity
            ):
                offer = offers_by_id[
                    offer_id
                ]
                product = offer.product

                offer_detail = _offer_detail(
                    offer
                )
                offer_description = (
                    f" ({offer_detail})"
                    if offer_detail
                    else ""
                )

                raise forms.ValidationError(
                    f"Only "
                    f"{product.stock_quantity_label(available_quantity)} "
                    f"available for "
                    f"{product.display_name}"
                    f"{offer_description}."
                )

        for (
            product_id,
            requested_quantity,
        ) in requested_quantity_by_product_id.items():
            if is_unusually_large_order_line(
                quantity=requested_quantity
            ):
                product = products_by_id[
                    product_id
                ]

                raise forms.ValidationError(
                    f"{product.display_name} is unusually large. "
                    f"Maximum is "
                    f"{product.stock_quantity_label(MAX_QUANTITY_PER_PRODUCT_PER_ORDER)} "
                    "per order."
                )

    @property
    def order_line_forms(
        self,
    ) -> list[OrderLineForm]:
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


def build_add_order_line_product_form(
    *,
    line_formset: OrderLineFormSet,
) -> AddOrderLineProductForm:
    return AddOrderLineProductForm(
        offer_queryset=(
            line_formset.offer_choice_context.queryset
        ),
        available_units_by_offer_id=(
            line_formset.offer_choice_context
            .available_units_by_offer_id
        ),
    )


def build_order_line_inputs(
    formset: BaseFormSet,
) -> list[BusinessOfferLineInput]:
    return [
        form.to_business_offer_line_input()
        for form in formset.order_line_forms
    ]


def build_order_line_initial_data(
    order: Order,
) -> list[dict[str, object]]:
    return [
        {
            "commercial_offer": (
                line.commercial_offer_id
            ),
            "unit": line.unit,
            "quantity": line.quantity_in_units,
            "offer_label": _order_line_offer_label(
                product=line.product,
                offer=line.commercial_offer,
            ),
        }
        for line in (
            order.lines
            .select_related(
                "product",
                "commercial_offer",
                "commercial_offer__batch",
            )
            .order_by("id")
        )
    ]


def _offer_detail(
    offer: CommercialPrice,
) -> str:
    # Ops is choosing a commercial offer, so show the commercial reason,
    # not the physical batch identity behind it. Standard is the normal
    # case and stays unlabeled to keep the picker visually quiet.
    if offer.batch_id is None:
        return ""

    if offer.reason:
        return str(
            offer.get_reason_display()
        )

    # Defensive fallback for legacy/incomplete batch offers.
    return f"Batch {offer.batch.batch_id}"


def _order_line_offer_label(
    *,
    product: Product,
    offer: CommercialPrice,
) -> str:
    product_label = (
        f"{product.code_label} · "
        f"{product.display_name} · "
        f"{product.unit_weight_label}"
    )
    offer_detail = _offer_detail(
        offer
    )

    if not offer_detail:
        return product_label

    return (
        f"{product_label} · "
        f"{offer_detail}"
    )


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
