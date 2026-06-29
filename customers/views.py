from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from common.table_controls import (
    TableControls,
    TableControlsTemplate,
    TableSortField,
)
from customers.detail_viewmodels import build_customer_detail_context
from customers.errors import InvalidCustomerData
from customers.form_viewmodels import (
    build_create_customer_form_context,
    build_edit_customer_form_context,
)
from customers.forms import (
    CustomerForm,
    build_customer_edit_initial_data,
)
from customers.list_viewmodels import (
    build_customer_page_rows,
    build_customers_page_header,
)
from customers.models import Customer
from customers.selectors import (
    CUSTOMER_SORTS,
    DEFAULT_CUSTOMER_SORT,
    list_customers,
)
from customers.services import create_customer, update_customer
from orders.selectors import (
    get_customer_order_summary,
)
from orders.selectors import (
    list_customer_orders as list_orders_for_customer,
)

CUSTOMERS_LIST_ANCHOR = "customers-list"

CUSTOMER_TABLE_SORTS = [
    TableSortField("customer", "Customer"),
    TableSortField("email", "Email"),
    TableSortField("phone", "Phone"),
    TableSortField("city", "City"),
    TableSortField("country", "Country"),
]

CUSTOMER_TABLE_CONTROLS_TEMPLATE = TableControlsTemplate(
    filters_title_id="customers-filters-title",
    filters_aria_label="Customer filters",
    sort_title_id="customers-sort-title",
    sort_select_id="mobile-customer-sort",
)


@login_required
def index(request):
    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=CUSTOMERS_LIST_ANCHOR,
        requested_sort=request.GET.get("sort", ""),
        filters=[],
        allowed_sorts=CUSTOMER_SORTS,
        default_sort=DEFAULT_CUSTOMER_SORT,
    )

    customers = list(
        list_customers(
            sort=controls.active_sort,
        )
    )

    context = {
        "page_header": build_customers_page_header(role_spec=request.role_spec),
        "customer_rows": build_customer_page_rows(customers),
        "filters": [],
        "table_sorts": controls.build_table_sort_links(CUSTOMER_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(CUSTOMER_TABLE_SORTS),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": CUSTOMER_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": [],
    }

    return render(request, "customers/index.html", context)


@login_required
def detail(request, customer_pk: int):
    customer = _get_customer_or_404(customer_pk)
    orders = list(list_orders_for_customer(customer=customer))

    context = build_customer_detail_context(
        customer=customer,
        order_summary=get_customer_order_summary(customer=customer),
        orders=orders,
        role_spec=request.role_spec,
        cancel_url=reverse("customers:index"),
    ).as_dict()

    return render(request, "customers/detail.html", context)


@login_required
def edit(request, customer_pk: int):
    customer = _get_customer_or_404(customer_pk)

    if request.method == "POST":
        form = CustomerForm(
            request.POST,
            customer=customer,
        )

        if form.is_valid():
            try:
                updated_customer = update_customer(
                    customer=customer,
                    user=request.user,
                    **form.cleaned_data,
                )
            except InvalidCustomerData as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Customer {updated_customer.name} updated.",
                )
                return redirect("customers:detail", customer_pk=updated_customer.pk)
    else:
        form = CustomerForm(
            initial=build_customer_edit_initial_data(customer),
            customer=customer,
        )

    context = build_edit_customer_form_context(
        form=form,
        customer=customer,
    ).as_dict()

    return render(request, "customers/customer_form.html", context)


@login_required
def create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)

        if form.is_valid():
            try:
                customer = create_customer(
                    **form.cleaned_data,
                    user=request.user,
                )
            except InvalidCustomerData as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Customer {customer.name} added.",
                )
                return redirect("customers:index")
    else:
        form = CustomerForm()

    context = build_create_customer_form_context(
        form=form,
    ).as_dict()

    return render(request, "customers/customer_form.html", context)


def _get_customer_or_404(customer_pk: int) -> Customer:
    return get_object_or_404(
        Customer.objects,
        pk=customer_pk,
    )
