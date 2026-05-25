from __future__ import annotations

from django import forms

from common.form_layout import set_form_field_layout
from products.catalog import (
    MAX_IMAGE_URL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_WEIGHT_PER_BOX,
    MIN_WEIGHT_PER_BOX,
)
from products.models import Product


PRODUCT_STATUS_ACTIVE = "active"
PRODUCT_STATUS_INACTIVE = "inactive"


def _configure_vegan_toggle(form: forms.BaseForm) -> None:
    field = form.fields["vegan"]
    field.tag_toggle = True
    field.tag_toggle_label = "Vegan"
    field.tag_toggle_icon = "leaf"
    field.tag_toggle_class = "product-tag-toggle product-tag-toggle--vegan"


class ProductForm(forms.Form):
    internal_number = forms.IntegerField(
        required=False,
        min_value=1,
        label="Internal number",
        help_text="Optional product number used in the customer catalog.",
        error_messages={
            "invalid": "Enter a whole number.",
            "min_value": "Internal number must be positive.",
        },
        widget=forms.NumberInput(
            #TODO Consider making thise a dataclass in common that standardizes the attributes for includes fields across the app.
            attrs={
                "placeholder": "e.g. 23",
                "inputmode": "numeric",
                "step": "1",
                "min": "1",
                "autocomplete": "off",
            }
        ),
    )

    manufacturer = forms.CharField(
        required=False,
        max_length=MAX_NAME_LENGTH,
        label="Manufacturer",
        help_text="Optional producer, e.g. Fazer, Cloetta, BUBS.",
        error_messages={
            "max_length": (
                f"Manufacturer cannot exceed {MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Fazer",
                "autocomplete": "organization",
            }
        ),
    )

    brand = forms.CharField(
        max_length=MAX_NAME_LENGTH,
        label="Brand",
        error_messages={
            "required": "Please enter the brand of the product.",
            "max_length": (
                f"Brand name cannot exceed {MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "organization",
                "placeholder": "e.g. Tutti Frutti",
            }
        ),
    )

    name = forms.CharField(
        max_length=MAX_NAME_LENGTH,
        label="Product name",
        help_text="Swedish/internal MVP product name.",
        error_messages={
            "required": "Please enter the name of the product.",
            "max_length": (
                f"Product name cannot exceed {MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. TYRKISK PEBER",
            }
        ),
    )

    weight_per_box = forms.IntegerField(
        min_value=MIN_WEIGHT_PER_BOX,
        max_value=MAX_WEIGHT_PER_BOX,
        label="Weight per box",
        help_text="Stored in grams. Cannot be changed after creation.",
        error_messages={
            "required": "Please enter the weight per box in grams.",
            "min_value": (
                f"Weight per box must be at least "
                f"{MIN_WEIGHT_PER_BOX} grams."
            ),
            "max_value": (
                f"Weight per box must be at most "
                f"{MAX_WEIGHT_PER_BOX} grams."
            ),
            "invalid": "Please enter a valid number for weight per box.",
        },
        widget=forms.NumberInput(
            attrs={
                "placeholder": "e.g. 3000",
                "inputmode": "numeric",
                "pattern": "[0-9]+",
                "autocomplete": "off",
            }
        ),
    )

    vegan = forms.BooleanField(
        required=False,
        label="Product attributes",
        widget=forms.CheckboxInput(
            attrs={
                "class": "product-tag-toggle__input",
            }
        ),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        _configure_vegan_toggle(self)

        set_form_field_layout(
            self,
            full=("name", "vegan"),
            half=(
                "internal_number",
                "manufacturer",
                "brand",
                "weight_per_box",
            ),
        )


class ProductEditForm(forms.Form):
    internal_number = forms.IntegerField(
        required=False,
        min_value=1,
        label="Internal number",
        help_text="Optional product number used in the customer catalog.",
        error_messages={
            "invalid": "Enter a whole number.",
            "min_value": "Internal number must be positive.",
        },
        widget=forms.NumberInput(
            attrs={
                "placeholder": "e.g. 23",
                "inputmode": "numeric",
                "step": "1",
                "min": "1",
                "autocomplete": "off",
            }
        ),
    )

    manufacturer = forms.CharField(
        required=False,
        max_length=MAX_NAME_LENGTH,
        label="Manufacturer",
        error_messages={
            "max_length": (
                f"Manufacturer cannot exceed {MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Fazer",
                "autocomplete": "organization",
            }
        ),
    )

    brand = forms.CharField(
        max_length=MAX_NAME_LENGTH,
        label="Brand",
        error_messages={
            "required": "Please enter the brand of the product.",
            "max_length": (
                f"Brand name cannot exceed {MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "organization",
                "placeholder": "e.g. Tutti Frutti",
            }
        ),
    )

    name = forms.CharField(
        max_length=MAX_NAME_LENGTH,
        label="Product name",
        help_text="Swedish/internal MVP product name.",
        error_messages={
            "required": "Please enter the name of the product.",
            "max_length": (
                f"Product name cannot exceed {MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. TYRKISK PEBER",
            }
        ),
    )

    active = forms.ChoiceField(
        choices=(
            (PRODUCT_STATUS_ACTIVE, "Active"),
            (PRODUCT_STATUS_INACTIVE, "Inactive"),
        ),
        label="Product status",
        error_messages={
            "required": "Choose product status.",
            "invalid_choice": "Choose a valid product status.",
        },
        widget=forms.RadioSelect(
            attrs={
                "class": "radio-chip-group",
            }
        ),
    )

    vegan = forms.BooleanField(
        required=False,
        label="Product attributes",
        widget=forms.CheckboxInput(
            attrs={
                "class": "product-tag-toggle__input",
            }
        ),
    )

    description = forms.CharField(
        required=False,
        label="Description",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Optional product description.",
            }
        ),
    )

    ingredients = forms.CharField(
        required=False,
        label="Ingredients",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Optional ingredients text.",
            }
        ),
    )

    image_url = forms.URLField(
        required=False,
        max_length=MAX_IMAGE_URL_LENGTH,
        label="Image URL",
        error_messages={
            "invalid": "Enter a valid image URL.",
            "max_length": (
                f"Image URL cannot exceed {MAX_IMAGE_URL_LENGTH} characters."
            ),
        },
        widget=forms.URLInput(
            attrs={
                "placeholder": "https://example.com/product.jpg",
                "autocomplete": "url",
            }
        ),
    )

    def __init__(self, *args, product: Product | None = None, **kwargs) -> None:
        self.product = product
        super().__init__(*args, **kwargs)

        _configure_vegan_toggle(self)

        set_form_field_layout(
            self,
            full=(
                "name",
                "active",
                "vegan",
                "description",
                "ingredients",
                "image_url",
            ),
            half=(
                "internal_number",
                "manufacturer",
                "brand",
            ),
        )

    @property
    def active_value(self) -> bool:
        return self.cleaned_data["active"] == PRODUCT_STATUS_ACTIVE


def build_product_edit_initial_data(product: Product) -> dict[str, object]:
    profile = getattr(product, "profile", None)

    return {
        "internal_number": product.internal_number,
        "manufacturer": product.manufacturer,
        "brand": product.brand,
        "name": product.name,
        "active": (
            PRODUCT_STATUS_ACTIVE
            if product.active
            else PRODUCT_STATUS_INACTIVE
        ),
        "vegan": product.vegan,
        "description": profile.description if profile is not None else "",
        "ingredients": profile.ingredients if profile is not None else "",
        "image_url": profile.image_url if profile is not None else "",
    }
