from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from common.table_controls import (
    TableControls,
    TableControlsTemplate,
    TableFilter,
    TableSortField,
)
from inventory.selectors import (
    available_quantity_by_product,
    list_available_batches_for_product,
)
from products.detail_viewmodels import build_product_detail_context
from products.errors import InvalidProductData
from products.forms import (
    ProductEditForm,
    ProductForm,
    build_product_edit_initial_data,
)
from products.form_viewmodels import build_product_context_items
from products.list_viewmodels import (
    build_product_page_rows,
    build_product_quick_jump_search,
    build_products_page_header,
    )
from products.models import Product
from products.selectors import (
    DEFAULT_PRODUCT_SORT,
    PRODUCT_FILTER_ACTIVE,
    PRODUCT_FILTER_ALL,
    PRODUCT_FILTER_INACTIVE,
    PRODUCT_SORTS,
    get_product_delivered_demand_summary,
    list_products,
)
from products.services import create_product, update_product


PRODUCT_FILTERS = [
    TableFilter(PRODUCT_FILTER_ALL, "All"),
    TableFilter(PRODUCT_FILTER_ACTIVE, "Active"),
    TableFilter(PRODUCT_FILTER_INACTIVE, "Inactive"),
]

PRODUCT_TABLE_SORTS = [
    TableSortField("number", "#"),
    TableSortField("product", "Product"),
    TableSortField("brand", "Brand"),
    TableSortField("manufacturer", "Manufacturer"),
    TableSortField("weight", "Weight"),
    TableSortField("unit", "Unit"),
    TableSortField("vegan", "Vegan"),
    TableSortField("status", "Status"),
]

PRODUCTS_LIST_ANCHOR = "products-list"
PRODUCT_FILTER_QUERY_KEY = "status"

PRODUCT_TABLE_CONTROLS_TEMPLATE = TableControlsTemplate(
    filters_title_id="products-filters-title",
    filters_aria_label="Product filters",
    sort_title_id="products-sort-title",
    sort_select_id="mobile-product-sort",
)


@login_required
def index(request):
    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=PRODUCTS_LIST_ANCHOR,
        requested_filter=request.GET.get(PRODUCT_FILTER_QUERY_KEY, ""),
        requested_sort=request.GET.get("sort", ""),
        filters=PRODUCT_FILTERS,
        allowed_sorts=PRODUCT_SORTS,
        default_sort=DEFAULT_PRODUCT_SORT,
        filter_query_key=PRODUCT_FILTER_QUERY_KEY,
    )

    products = list(
        list_products(
            status=controls.active_filter,
            sort=controls.active_sort,
        )
    )

    product_rows = build_product_page_rows(products)

    context = {
        "page_header": build_products_page_header(role_spec=request.role_spec),
        "product_rows": product_rows,
        "quick_jump_search": build_product_quick_jump_search(product_rows), 
        "filters": controls.build_filter_links(PRODUCT_FILTERS), 
        "table_sorts": controls.build_table_sort_links(PRODUCT_TABLE_SORTS), 
        "mobile_sort_fields": controls.build_mobile_sort_fields(PRODUCT_TABLE_SORTS), 
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": PRODUCT_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": ["number", "weight"],
    }

    return render(request, "products/index.html", context)


@login_required
def detail(request, product_pk: int):
    product = _get_product_or_404(product_pk)

    context = build_product_detail_context(
        product=product,
        stock_row=_get_stock_row_for_product(product),
        active_batches=list(
            list_available_batches_for_product(product=product)
        ),
        demand_summary=get_product_delivered_demand_summary(product=product),
        role_spec=request.role_spec,
        cancel_url=reverse("products:index"),
    ).as_dict()

    return render(request, "products/detail.html", context)


@login_required
def edit(request, product_pk: int):
    product = _get_product_or_404(product_pk)

    if request.method == "POST":
        form = ProductEditForm(
            request.POST,
            product=product,
        )

        if form.is_valid():
            try:
                updated_product = update_product(
                    product=product,
                    internal_number=form.cleaned_data["internal_number"],
                    manufacturer=form.cleaned_data["manufacturer"],
                    brand=form.cleaned_data["brand"],
                    name=form.cleaned_data["name"],
                    active=form.active_value,
                    vegan=form.cleaned_data["vegan"],
                    description=form.cleaned_data["description"],
                    ingredients=form.cleaned_data["ingredients"],
                    image_url=form.cleaned_data["image_url"],
                    user=request.user,
                )
            except InvalidProductData as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Product {updated_product.sku} updated.",
                )
                return redirect("products:detail", product_pk=updated_product.pk)
    else:
        form = ProductEditForm(
            initial=build_product_edit_initial_data(product),
            product=product,
        )

    context = {
        "form": form,
        "product": product,
        "product_context_items": build_product_context_items(product),
        "title": f"Edit - {product.display_name}",
        "description": "",
        "submit_label": "Update product",
        "cancel_url": reverse("products:detail", kwargs={"product_pk": product.pk}),
    }

    return render(request, "products/product_form.html", context)


@login_required
def create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)

        if form.is_valid():
            try:
                result = create_product(
                    **form.cleaned_data,
                    user=request.user,
                )
            except InvalidProductData as error:
                form.add_error(None, str(error))
            else:
                if result.created:
                    messages.success(request, result.message)
                else:
                    messages.info(request, result.message)

                return redirect("products:index")
    else:
        form = ProductForm()

    context = {
        "form": form,
        "title": "Add product",
        "description": "",
        "submit_label": "Add product",
        "cancel_url": reverse("products:index"),
    }

    return render(request, "products/product_form.html", context)


def _get_product_or_404(product_pk: int) -> Product:
    return get_object_or_404(
        Product.objects.select_related("profile"),
        pk=product_pk,
    )


def _get_stock_row_for_product(product: Product):
    for row in available_quantity_by_product():
        if row.product_id == product.pk:
            return row

    return None
