from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from common.table_controls import (
    TableControls,
    TableControlsTemplate,
    TableFilter,
    TableSortField,
)
from customer_portal.detail_viewmodels import (
    build_portal_order_detail_context,
)
from customer_portal.order_list_viewmodels import (
    build_portal_order_page_rows,
    build_portal_orders_page_header,
)
from customer_portal.selectors import (
    get_portal_customer_for_user,
    get_portal_order_for_user,
)
from customer_portal.viewmodels import (
    RECENT_PORTAL_ORDER_LIMIT,
    build_portal_home_context,
)
from orders.models import Order
from orders.selectors import (
    CUSTOMER_ORDER_SORTS,
    DEFAULT_CUSTOMER_ORDER_SORT,
    get_customer_order_summary,
    list_customer_orders,
)


PORTAL_ORDERS_LIST_ANCHOR = "portal-orders-list"
PORTAL_ORDER_FILTER_QUERY_KEY = "status"

PORTAL_ORDER_FILTERS = [
    TableFilter("", gettext_lazy("All")),
    TableFilter(Order.Status.PLACED, Order.Status.PLACED.label),
    TableFilter(Order.Status.PACKED, Order.Status.PACKED.label),
    TableFilter(Order.Status.DELIVERED, Order.Status.DELIVERED.label),
    TableFilter(Order.Status.CANCELLED, Order.Status.CANCELLED.label),
]

PORTAL_ORDER_TABLE_SORTS = [
    TableSortField("order", gettext_lazy("Order")),
    TableSortField("created", gettext_lazy("Created")),
    TableSortField("status", gettext_lazy("Status")),
    TableSortField("quantity", gettext_lazy("Quantity")),
]

PORTAL_ORDER_TABLE_CONTROLS_TEMPLATE = TableControlsTemplate(
    filters_title_id="portal-orders-filters-title",
    filters_aria_label=gettext_lazy("Order filters"),
    sort_title_id="portal-orders-sort-title",
    sort_select_id="mobile-portal-orders-sort",
)


@login_required
def index(request):
    customer = get_portal_customer_for_user(user=request.user)

    context = build_portal_home_context(
        customer=customer,
        order_summary=get_customer_order_summary(customer=customer),
        recent_orders=tuple(
            list_customer_orders(customer=customer)[:RECENT_PORTAL_ORDER_LIMIT]
        ),
    ).as_dict()

    return render(request, "customer_portal/index.html", context)


@login_required
def orders(request):
    customer = get_portal_customer_for_user(user=request.user)

    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=PORTAL_ORDERS_LIST_ANCHOR,
        requested_filter=request.GET.get(PORTAL_ORDER_FILTER_QUERY_KEY, ""),
        requested_sort=request.GET.get("sort", ""),
        filters=PORTAL_ORDER_FILTERS,
        allowed_sorts=CUSTOMER_ORDER_SORTS,
        default_sort=DEFAULT_CUSTOMER_ORDER_SORT,
        filter_query_key=PORTAL_ORDER_FILTER_QUERY_KEY,
    )

    customer_orders = list(
        list_customer_orders(
            customer=customer,
            status=controls.active_filter or None,
            sort=controls.active_sort,
        )
    )

    context = {
        "page_header": build_portal_orders_page_header(),
        "order_rows": build_portal_order_page_rows(
            orders=customer_orders,
        ),
        "filters": controls.build_filter_links(PORTAL_ORDER_FILTERS),
        "table_sorts": controls.build_table_sort_links(PORTAL_ORDER_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(
            PORTAL_ORDER_TABLE_SORTS
        ),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": PORTAL_ORDER_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": ["quantity"],
    }

    return render(request, "customer_portal/orders.html", context)


@login_required
def place_order(request):
    return HttpResponse(_("Place order"))


@login_required
def order_detail(request, order_id: int):
    order = get_portal_order_for_user(
        user=request.user,
        order_id=order_id,
    )

    context = build_portal_order_detail_context(
        order=order,
    ).as_dict()

    return render(request, "customer_portal/order_detail.html", context)


@login_required
def catalog(request):
    return HttpResponse(_("Customer catalog"))


@login_required
def profile(request):
    return HttpResponse(_("My profile"))


@login_required
def edit_profile(request):
    return HttpResponse(_("Edit my profile"))


@login_required
def contact(request):
    return HttpResponse(_("Contact SwedeSweets"))
