from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from products.forms import ProductEditForm, ProductForm
from products.models import Product


@dataclass(frozen=True, slots=True)
class FormContextItem:
    label: str
    value: Any


@dataclass(frozen=True, slots=True)
class ProductFormContext:
    form: ProductForm | ProductEditForm
    title: str
    description: str
    submit_label: str
    cancel_url: str
    product: Product | None = None
    product_context_items: list[FormContextItem] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "form": self.form,
            "product": self.product,
            "product_context_items": self.product_context_items or [],
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
        }


def build_create_product_form_context(
    *,
    form: ProductForm,
) -> ProductFormContext:
    return ProductFormContext(
        form=form,
        title="Add product",
        description="",
        submit_label="Add product",
        cancel_url=reverse("products:index"),
    )


def build_edit_product_form_context(
    *,
    form: ProductEditForm,
    product: Product,
) -> ProductFormContext:
    return ProductFormContext(
        form=form,
        product=product,
        product_context_items=build_product_context_items(product),
        title=f"Edit - {product.display_name}",
        description="",
        submit_label="Update product",
        cancel_url=reverse("products:detail", kwargs={"product_pk": product.pk}),
    )


def build_product_context_items(product: Product) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="SKU",
            value=product.sku,
        ),
        FormContextItem(
            label="Unit weight",
            value=product.unit_weight_label,
        ),
        FormContextItem(
            label="Stock unit",
            value=product.get_stock_unit_display(),
        ),
        FormContextItem(
            label="Current status",
            value="Active" if product.active else "Inactive",
        ),
    ]
