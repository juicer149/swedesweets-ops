from __future__ import annotations

from django import forms

from common.form_layout import set_form_field_layout
from inventory.models import InventoryBatch
from products.models import Product


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product: Product) -> str:
        return product.catalog_label


class BatchForm(forms.Form):
    batch_id = forms.CharField(
        required=False,
        max_length=50,
        label="Batch ID",
        help_text="Leave empty to generate one automatically.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. AHL-20260523-01",
                "autocomplete": "off",
            }
        ),
    )

    product = ProductChoiceField(
        queryset=Product.objects.filter(active=True).order_by(
            "internal_number",
            "brand",
            "name",
            "weight_per_box",
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

    boxes = forms.IntegerField(
        min_value=1,
        label="Boxes",
        error_messages={
            "required": "Enter number of boxes.",
            "invalid": "Enter a whole number of boxes.",
            "min_value": "A new batch must contain at least 1 box.",
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
            half=("batch_id", "boxes", "best_before", "location"),
        )


class BatchEditForm(forms.Form):
    boxes = forms.IntegerField(
        min_value=0,
        label="Boxes",
        help_text="Set the physical box count after stock correction.",
        error_messages={
            "required": "Enter number of boxes.",
            "invalid": "Enter a whole number of boxes.",
            "min_value": "Boxes cannot be negative.",
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
            half=("boxes", "best_before", "location"),
        )


def build_batch_edit_initial_data(batch: InventoryBatch) -> dict[str, object]:
    return {
        "boxes": batch.boxes,
        "best_before": batch.best_before,
        "location": batch.location,
    }
