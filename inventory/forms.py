from __future__ import annotations

from django import forms

from common.form_layout import set_form_field_layout
from inventory.models import InventoryBatch
from products.models import Product


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product: Product) -> str:
        return product.catalog_label


class BatchForm(forms.Form):
    product = ProductChoiceField(
        queryset=Product.objects.filter(active=True).order_by(
            "internal_number",
            "brand",
            "name",
            "weight_per_unit",
        ),
        label="Product",
        empty_label="Choose product",
        error_messages={
            "required": "Choose a product.",
            "invalid_choice": "Choose a valid active product.",
        },
        widget=forms.Select(
            attrs={
                "data-enhanced-select": "true",
                "data-enhanced-select-search": "true",
            }
        ),
    )

    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity",
        help_text="Number of product stock units received for this batch.",
        error_messages={
            "required": "Enter quantity.",
            "invalid": "Enter a whole number.",
            "min_value": "A new batch must contain at least 1 unit.",
        },
        widget=forms.NumberInput(
            attrs={
                "min": "1",
                "step": "1",
                "inputmode": "numeric",
            }
        ),
    )

    best_before = forms.DateField(
        label="Best before",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
            },
        ),
        error_messages={
            "required": "Enter a best-before date.",
            "invalid": "Enter a valid date.",
        },
    )

    location = forms.CharField(
        max_length=120,
        label="Location",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Shelf A1",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            full=("product",),
            half=("quantity", "best_before", "location"),
        )


class BatchEditForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=0,
        label="Quantity",
        help_text="Set the physical stock-unit count after stock correction.",
        error_messages={
            "required": "Enter quantity.",
            "invalid": "Enter a whole number.",
            "min_value": "Quantity cannot be negative.",
        },
        widget=forms.NumberInput(
            attrs={
                "min": "0",
                "step": "1",
                "inputmode": "numeric",
            }
        ),
    )

    best_before = forms.DateField(
        label="Best before",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
            },
        ),
        error_messages={
            "required": "Enter a best-before date.",
            "invalid": "Enter a valid date.",
        },
    )

    location = forms.CharField(
        max_length=120,
        label="Location",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Shelf A1",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, batch: InventoryBatch | None = None, **kwargs) -> None:
        self.batch = batch
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            half=("quantity", "best_before", "location"),
        )


def build_batch_edit_initial_data(batch: InventoryBatch) -> dict[str, object]:
    return {
        "quantity": batch.quantity,
        "best_before": batch.best_before,
        "location": batch.location,
    }
