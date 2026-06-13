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
from inventory.access import can_close_batch, can_edit_batch
from inventory.detail_viewmodels import (
    build_batch_detail_context,
)
from inventory.errors import InvalidStockOperation
from inventory.forms import (
    BatchEditForm,
    BatchForm,
    build_batch_edit_initial_data,
)
from inventory.form_viewmodels import (
    build_close_batch_form_context,
    build_create_batch_form_context,
    build_edit_batch_form_context,
)
from inventory.list_viewmodels import (
    build_batch_page_rows,
    build_batch_quick_jump_search,
    build_inventory_page_header,
    build_inventory_view_links,
    build_product_stock_page_rows,
    build_product_stock_quick_jump_search,
)
from inventory.models import InventoryBatch
from inventory.selectors import (
    BATCH_SORTS,
    DEFAULT_BATCH_SORT,
    DEFAULT_PRODUCT_STOCK_SORT,
    PRODUCT_STOCK_SORTS,
    available_quantity_by_product,
    list_batch_allocations,
    list_batch_rows,
    sort_available_stock_rows,
)
from inventory.services import close_batch, create_batch, update_batch


INVENTORY_VIEW_BATCHES = "batches"
INVENTORY_VIEW_PRODUCTS = "products"
INVENTORY_DEFAULT_VIEW = INVENTORY_VIEW_BATCHES
INVENTORY_ALLOWED_VIEWS = {
    INVENTORY_VIEW_BATCHES,
    INVENTORY_VIEW_PRODUCTS,
}

INVENTORY_FILTERS = [
    TableFilter("", "All"),
    TableFilter(InventoryBatch.Status.ACTIVE, "Active"),
    TableFilter(InventoryBatch.Status.DEPLETED, "Depleted"),
    TableFilter(InventoryBatch.Status.CLOSED, "Closed"),
]

BATCH_TABLE_SORTS = [
    TableSortField("batch", "Batch"),
    TableSortField("product", "Product"),
    TableSortField("best_before", "Best before"),
    TableSortField("quantity", "Quantity"),
    TableSortField("status", "Status"),
    TableSortField("location", "Location"),
]

PRODUCT_STOCK_TABLE_SORTS = [
    TableSortField("product", "Product"),
    TableSortField("batches", "Batches"),
    TableSortField("unit", "Unit"),
    TableSortField("physical", "In stock"),
    TableSortField("reserved", "Reserved"),
    TableSortField("available", "Available"),
]

INVENTORY_LIST_ANCHOR = "inventory-list"
INVENTORY_FILTER_QUERY_KEY = "status"
INVENTORY_VIEW_QUERY_KEY = "view"

INVENTORY_TABLE_CONTROLS_TEMPLATE = TableControlsTemplate(
    filters_title_id="inventory-filters-title",
    filters_aria_label="Inventory filters",
    sort_title_id="inventory-sort-title",
    sort_select_id="mobile-inventory-sort",
)


@login_required
def index(request):
    active_view = _active_inventory_view(
        request.GET.get(INVENTORY_VIEW_QUERY_KEY, "")
    )

    if active_view == INVENTORY_VIEW_PRODUCTS:
        context = _build_products_index_context(request)
    else:
        context = _build_batches_index_context(request)

    return render(request, "inventory/index.html", context)


@login_required
def detail(request, batch_pk: int):
    batch = _get_batch_or_404(batch_pk)
    allocations = list_batch_allocations(batch=batch)

    context = build_batch_detail_context(
        batch=batch,
        allocations=allocations,
        cancel_url=reverse("inventory:index"),
        role_spec=request.role_spec,
    ).as_dict()

    return render(request, "inventory/detail.html", context)


@login_required
def edit(request, batch_pk: int):
    batch = _get_batch_or_404(batch_pk)

    if not can_edit_batch(batch=batch, role_spec=request.role_spec):
        messages.error(
            request,
            f"Batch {batch.batch_id} cannot be edited.",
        )
        return redirect("inventory:detail", batch_pk=batch.pk)

    if request.method == "POST":
        form = BatchEditForm(
            request.POST,
            batch=batch,
        )

        if form.is_valid():
            try:
                updated_batch = update_batch(
                    batch=batch,
                    quantity=form.cleaned_data["quantity"],
                    best_before=form.cleaned_data["best_before"],
                    location=form.cleaned_data["location"],
                    user=request.user,
                )
            except InvalidStockOperation as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Batch {updated_batch.batch_id} updated.",
                )
                return redirect("inventory:detail", batch_pk=updated_batch.pk)
    else:
        form = BatchEditForm(
            initial=build_batch_edit_initial_data(batch),
            batch=batch,
        )

    context = build_edit_batch_form_context(
        form=form,
        batch=batch,
        cancel_url=reverse("inventory:detail", kwargs={"batch_pk": batch.pk}),
    ).as_dict()

    return render(request, "inventory/batch_form.html", context)


@login_required
def create(request):
    if request.method == "POST":
        form = BatchForm(request.POST)

        if form.is_valid():
            try:
                batch = create_batch(
                    **form.cleaned_data,
                    user=request.user,
                )
            except InvalidStockOperation as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Batch {batch.batch_id} added.",
                )
                return redirect("inventory:index")
    else:
        form = BatchForm()

    context = build_create_batch_form_context(
        form=form,
        cancel_url=reverse("inventory:index"),
    ).as_dict()

    return render(request, "inventory/batch_form.html", context)


@login_required
def close(request, batch_pk: int):
    batch = _get_batch_or_404(batch_pk)

    if not can_close_batch(batch=batch, role_spec=request.role_spec):
        messages.error(
            request,
            f"Batch {batch.batch_id} cannot be closed.",
        )
        return redirect("inventory:detail", batch_pk=batch.pk)

    if request.method == "POST":
        try:
            closed_batch = close_batch(
                batch=batch,
                user=request.user,
            )
        except InvalidStockOperation as error:
            messages.error(request, str(error))
            return redirect("inventory:detail", batch_pk=batch.pk)

        messages.success(
            request,
            f"Batch {closed_batch.batch_id} closed.",
        )
        return redirect("inventory:detail", batch_pk=closed_batch.pk)

    context = build_close_batch_form_context(
        batch=batch,
        cancel_url=reverse("inventory:detail", kwargs={"batch_pk": batch.pk}),
    ).as_dict()

    return render(request, "inventory/close.html", context)


def _build_batches_index_context(request) -> dict[str, object]:
    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=INVENTORY_LIST_ANCHOR,
        requested_filter=request.GET.get(INVENTORY_FILTER_QUERY_KEY, ""),
        requested_sort=request.GET.get("sort", ""),
        filters=INVENTORY_FILTERS,
        allowed_sorts=BATCH_SORTS,
        default_sort=DEFAULT_BATCH_SORT,
        filter_query_key=INVENTORY_FILTER_QUERY_KEY,
    )

    batch_page_rows = build_batch_page_rows(
        list_batch_rows(
            status=controls.active_filter or None,
            sort=controls.active_sort,
        )
    )

    return {
        "page_header": build_inventory_page_header(role_spec=request.role_spec),
        "active_view": INVENTORY_VIEW_BATCHES,
        "view_links": _inventory_view_links(active_view=INVENTORY_VIEW_BATCHES),
        "quick_jump_search": build_batch_quick_jump_search(batch_page_rows),
        "inventory_rows": batch_page_rows,
        "product_rows": [],
        "filters": controls.build_filter_links(INVENTORY_FILTERS),
        "table_sorts": controls.build_table_sort_links(BATCH_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(BATCH_TABLE_SORTS),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": INVENTORY_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": ["quantity"],
    }


def _build_products_index_context(request) -> dict[str, object]:
    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=INVENTORY_LIST_ANCHOR,
        requested_filter="",
        requested_sort=request.GET.get("sort", ""),
        filters=[],
        allowed_sorts=PRODUCT_STOCK_SORTS,
        default_sort=DEFAULT_PRODUCT_STOCK_SORT,
        filter_query_key=INVENTORY_FILTER_QUERY_KEY,
        extra_query_params={
            INVENTORY_VIEW_QUERY_KEY: INVENTORY_VIEW_PRODUCTS,
        },
    )

    product_page_rows = build_product_stock_page_rows(
        sort_available_stock_rows(
            rows=available_quantity_by_product(),
            sort=controls.active_sort,
        )
    )

    return {
        "page_header": build_inventory_page_header(role_spec=request.role_spec),
        "active_view": INVENTORY_VIEW_PRODUCTS,
        "view_links": _inventory_view_links(active_view=INVENTORY_VIEW_PRODUCTS),
        "quick_jump_search": build_product_stock_quick_jump_search(product_page_rows),
        "inventory_rows": [],
        "product_rows": product_page_rows,
        "filters": [],
        "table_sorts": controls.build_table_sort_links(PRODUCT_STOCK_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(
            PRODUCT_STOCK_TABLE_SORTS
        ),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": INVENTORY_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": [
            "batches",
            "physical",
            "reserved",
            "available",
        ],
    }


def _inventory_view_links(
    *,
    active_view: str,
):
    return build_inventory_view_links(
        active_view=active_view,
        batches_href=f"{reverse('inventory:index')}?view={INVENTORY_VIEW_BATCHES}",
        products_href=f"{reverse('inventory:index')}?view={INVENTORY_VIEW_PRODUCTS}",
    )


def _active_inventory_view(value: str) -> str:
    if value in INVENTORY_ALLOWED_VIEWS:
        return value

    return INVENTORY_DEFAULT_VIEW


def _get_batch_or_404(batch_pk: int) -> InventoryBatch:
    return get_object_or_404(
        InventoryBatch.objects.select_related("product"),
        pk=batch_pk,
    )
