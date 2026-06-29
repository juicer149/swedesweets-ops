from __future__ import annotations

from django import forms

from common.form_layout import set_form_field_layout
from products.catalog import (
    MAX_IMAGE_URL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_WEIGHT_PER_UNIT,
    MIN_WEIGHT_PER_UNIT,
)
from products.models import Product

PRODUCT_STATUS_ACTIVE = "active"
PRODUCT_STATUS_INACTIVE = "inactive"

CUSTOMER_FACING_LANGUAGE_CODE = "fr"


def _configure_vegan_toggle(form: forms.BaseForm) -> None:
    field = form.fields["vegan"]
    field.tag_toggle = True
    field.tag_toggle_label = "Vegan"
    field.tag_toggle_icon = "leaf"
    field.tag_toggle_class = "product-tag-toggle product-tag-toggle--vegan"


def _customer_facing_name_fr_field() -> forms.CharField:
    return forms.CharField(
        required=False,
        max_length=MAX_NAME_LENGTH,
        label="Customer-facing French name",
        help_text=("Optional. Used in the customer portal when French is selected."),
        error_messages={
            "max_length": (
                f"Customer-facing French name cannot exceed "
                f"{MAX_NAME_LENGTH} characters."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Tutti Frutti Acidulé",
            }
        ),
    )


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
            "max_length": (f"Manufacturer cannot exceed {MAX_NAME_LENGTH} characters."),
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
            "max_length": (f"Brand name cannot exceed {MAX_NAME_LENGTH} characters."),
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
            "max_length": (f"Product name cannot exceed {MAX_NAME_LENGTH} characters."),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. TYRKISK PEBER",
            }
        ),
    )

    customer_facing_name_fr = _customer_facing_name_fr_field()

    stock_unit = forms.ChoiceField(
        choices=Product.StockUnit.choices,
        initial=Product.StockUnit.BOX,
        label="Stock unit",
        help_text="How this product is counted in inventory and orders.",
        error_messages={
            "required": "Choose a stock unit.",
            "invalid_choice": "Choose a valid stock unit.",
        },
        widget=forms.RadioSelect(
            attrs={
                "class": "radio-chip-group",
            }
        ),
    )

    weight_per_unit = forms.IntegerField(
        min_value=MIN_WEIGHT_PER_UNIT,
        max_value=MAX_WEIGHT_PER_UNIT,
        label="Weight per unit",
        help_text="Stored in grams. Cannot be changed after creation.",
        error_messages={
            "required": "Please enter the weight per unit in grams.",
            "min_value": (
                f"Weight per unit must be at least {MIN_WEIGHT_PER_UNIT} grams."
            ),
            "max_value": (
                f"Weight per unit must be at most {MAX_WEIGHT_PER_UNIT} grams."
            ),
            "invalid": "Please enter a valid number for weight per unit.",
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
            full=(
                "customer_facing_name_fr",
                "vegan",
            ),
            half=(
                "internal_number",
                "manufacturer",
                "brand",
                "name",
                "stock_unit",
                "weight_per_unit",
            ),
        )


# TODO: Model pack sizes/product variants before allowing stock_unit or
# weight_per_unit edits. Existing batches and orders depend on these values.
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
            "max_length": (f"Manufacturer cannot exceed {MAX_NAME_LENGTH} characters."),
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
            "max_length": (f"Brand name cannot exceed {MAX_NAME_LENGTH} characters."),
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
            "max_length": (f"Product name cannot exceed {MAX_NAME_LENGTH} characters."),
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. TYRKISK PEBER",
            }
        ),
    )

    customer_facing_name_fr = _customer_facing_name_fr_field()

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
                "customer_facing_name_fr",
                "description",
                "ingredients",
                "image_url",
            ),
            half=(
                "internal_number",
                "manufacturer",
                "brand",
                "name",
                "active",
                "vegan",
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
        "customer_facing_name_fr": _product_translation_name(
            product,
            language_code=CUSTOMER_FACING_LANGUAGE_CODE,
        ),
        "active": (
            PRODUCT_STATUS_ACTIVE if product.active else PRODUCT_STATUS_INACTIVE
        ),
        "vegan": product.vegan,
        "description": profile.description if profile is not None else "",
        "ingredients": profile.ingredients if profile is not None else "",
        "image_url": profile.image_url if profile is not None else "",
    }


def _product_translation_name(
    product: Product,
    *,
    language_code: str,
) -> str:
    translation = product.translations.filter(language_code=language_code).first()

    if translation is None:
        return ""

    return translation.name
