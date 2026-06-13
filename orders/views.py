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
from inventory.errors import InvalidStockOperation
from orders.access import can_cancel_order
from orders.detail_viewmodels import (
    build_deliver_action,
    build_order_cancel_back_url,
    build_order_detail_context,
    build_order_detail_primary_action,
    build_order_secondary_actions,
    build_pack_action,
    build_post_edit_success_url,
    build_post_pack_success_url,
)
from orders.errors import InvalidOrderOperation
from orders.form_viewmodels import (
    build_create_order_form_context,
    build_edit_order_form_context,
)
from orders.forms import (
    OrderCancelForm,
    OrderCreateForm,
    OrderLineFormSet,
    build_order_line_initial_data,
    build_order_line_inputs,
)
from orders.list_viewmodels import (
    build_order_page_rows,
    build_orders_page_header,
)
from orders.models import Order
from orders.selectors import (
    DEFAULT_ORDER_SORT,
    ORDER_SORTS,
    get_packaging_list,
    list_orders,
)
from orders.services import (
    cancel_order,
    create_order,
    deliver_order,
    pack_order,
    update_placed_order,
)


ORDER_FILTERS = [
    TableFilter("", "All"),
    TableFilter(Order.Status.PLACED, "Placed"),
    TableFilter(Order.Status.PACKED, "Packed"),
    TableFilter(Order.Status.DELIVERED, "Delivered"),
    TableFilter(Order.Status.CANCELLED, "Cancelled"),
]

ORDER_TABLE_SORTS = [
    TableSortField("order", "Order"),
    TableSortField("customer", "Customer"),
    TableSortField("created", "Created"),
    TableSortField("status", "Status"),
    TableSortField("quantity", "Quantity"),
]

ORDERS_LIST_ANCHOR = "orders-list"
ORDER_FILTER_QUERY_KEY = "status"
ORDER_LINE_FORMSET_PREFIX = "lines"

ORDER_TABLE_CONTROLS_TEMPLATE = TableControlsTemplate(
    filters_title_id="orders-filters-title",
    filters_aria_label="Order filters",
    sort_title_id="mobile-order-sort",
    sort_select_id="mobile-order-sort",
)

ORDER_OPERATION_ERRORS = (
    InvalidOrderOperation,
    InvalidStockOperation,
)


@login_required
def index(request):
    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=ORDERS_LIST_ANCHOR,
        requested_filter=request.GET.get(ORDER_FILTER_QUERY_KEY, ""),
        requested_sort=request.GET.get("sort", ""),
        filters=ORDER_FILTERS,
        allowed_sorts=ORDER_SORTS,
        default_sort=DEFAULT_ORDER_SORT,
        filter_query_key=ORDER_FILTER_QUERY_KEY,
    )

    orders = list(
        list_orders(
            status=controls.active_filter or None,
            sort=controls.active_sort,
        )
    )

    context = {
        "page_header": build_orders_page_header(role_spec=request.role_spec),
        "order_rows": build_order_page_rows(
            orders=orders,
            role_spec=request.role_spec,
        ),
        "filters": controls.build_filter_links(ORDER_FILTERS),
        "table_sorts": controls.build_table_sort_links(ORDER_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(ORDER_TABLE_SORTS),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": ORDER_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": ["quantity"],
    }

    return render(request, "orders/index.html", context)


@login_required
def create(request):
    if request.method == "POST":
        form = OrderCreateForm(request.POST)
        line_formset = OrderLineFormSet(
            request.POST,
            prefix=ORDER_LINE_FORMSET_PREFIX,
        )

        if form.is_valid() and line_formset.is_valid():
            try:
                order = create_order(
                    customer=form.cleaned_data["customer"],
                    lines=build_order_line_inputs(line_formset),
                    user=request.user,
                )
            except ORDER_OPERATION_ERRORS as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Order #{order.id} placed.",
                )
                return redirect("orders:index")
    else:
        form = OrderCreateForm()
        line_formset = OrderLineFormSet(prefix=ORDER_LINE_FORMSET_PREFIX)

    context = build_create_order_form_context(
        form=form,
        line_formset=line_formset,
    ).as_dict()

    return render(request, "orders/order_form.html", context)


@login_required
def edit(request, order_id: int):
    order = _get_order_or_404(order_id)

    if not order.can_be_edited:
        messages.error(
            request,
            f"Order #{order.id} cannot be edited because it is {order.status}.",
        )
        return redirect("orders:detail", order_id=order.id)

    if request.method == "POST":
        line_formset = OrderLineFormSet(
            request.POST,
            prefix=ORDER_LINE_FORMSET_PREFIX,
            order=order,
        )

        if line_formset.is_valid():
            try:
                updated_order = update_placed_order(
                    order=order,
                    lines=build_order_line_inputs(line_formset),
                    user=request.user,
                )
            except ORDER_OPERATION_ERRORS as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request,
                    f"Order #{updated_order.id} updated.",
                )
                return redirect(
                    build_post_edit_success_url(
                        order=updated_order,
                        role_spec=request.role_spec,
                    )
                )
    else:
        line_formset = OrderLineFormSet(
            initial=build_order_line_initial_data(order),
            prefix=ORDER_LINE_FORMSET_PREFIX,
            order=order,
        )

    context = build_edit_order_form_context(
        order=order,
        line_formset=line_formset,
    ).as_dict()

    context["cancel_order_url"] = (
        reverse("orders:cancel", kwargs={"order_id": order.id})
        if can_cancel_order(order=order, role_spec=request.role_spec)
        else ""
    )

    return render(request, "orders/order_form.html", context)


@login_required
def cancel(request, order_id: int):
    order = _get_order_or_404(order_id)

    if not order.can_be_cancelled:
        messages.error(
            request,
            f"Order #{order.id} cannot be cancelled because it is {order.status}.",
        )
        return redirect("orders:detail", order_id=order.id)

    if request.method == "POST":
        form = OrderCancelForm(request.POST)

        if form.is_valid():
            try:
                cancelled_order = cancel_order(
                    order=order,
                    user=request.user,
                    reason=form.cleaned_data["reason"],
                    note=form.cleaned_data["note"],
                )
            except InvalidOrderOperation as error:
                messages.error(request, str(error))
                return redirect("orders:detail", order_id=order.id)

            messages.success(
                request,
                f"Order #{cancelled_order.id} cancelled.",
            )
            return redirect("orders:detail", order_id=cancelled_order.id)
    else:
        form = OrderCancelForm()

    context = build_order_detail_context(
        order=order,
        title=f"Cancel order #{order.id}",
        description="",
        cancel_url=build_order_cancel_back_url(
            order=order,
            role_spec=request.role_spec,
        ),
        active_panel="order",
        include_contents=True,
    ).as_dict()

    context["form"] = form
    context["submit_label"] = "Cancel order"

    return render(request, "orders/cancel.html", context)


@login_required
def pack(request, order_id: int):
    order = _get_order_or_404(order_id)

    if order.status != Order.Status.PLACED:
        messages.error(
            request,
            f"Order #{order.id} cannot be packed because it is {order.status}.",
        )
        return redirect("orders:detail", order_id=order.id)

    if request.method == "POST":
        try:
            packed_order = pack_order(order=order, user=request.user)
        except ORDER_OPERATION_ERRORS as error:
            messages.error(request, str(error))
            return redirect("orders:pack", order_id=order.id)

        messages.success(
            request,
            f"Order #{packed_order.id} packed.",
        )
        return redirect(
            build_post_pack_success_url(
                order=packed_order,
                role_spec=request.role_spec,
            )
        )

    pick_lines = get_packaging_list(order=order)

    context = build_order_detail_context(
        order=order,
        title=f"Pack order #{order.id}",
        description="",
        cancel_url=reverse("orders:index"),
        active_panel="",
        include_contents=True,
        pick_lines=pick_lines,
        primary_action=build_pack_action(is_disabled=not pick_lines),
        secondary_actions=build_order_secondary_actions(
            order=order,
            role_spec=request.role_spec,
        ),
    ).as_dict()

    return render(request, "orders/pack.html", context)


@login_required
def deliver(request, order_id: int):
    order = _get_order_or_404(order_id)

    if order.status != Order.Status.PACKED:
        messages.error(
            request,
            f"Order #{order.id} cannot be delivered because it is {order.status}.",
        )
        return redirect("orders:detail", order_id=order.id)

    if request.method == "POST":
        try:
            delivered_order = deliver_order(order=order, user=request.user)
        except InvalidOrderOperation as error:
            messages.error(request, str(error))
            return redirect("orders:deliver", order_id=order.id)

        messages.success(
            request,
            f"Order #{delivered_order.id} delivered.",
        )
        return redirect("orders:detail", order_id=delivered_order.id)

    context = build_order_detail_context(
        order=order,
        title=f"Deliver order #{order.id}",
        description="",
        cancel_url=reverse("orders:index"),
        active_panel="contents",
        include_contents=True,
        primary_action=build_deliver_action(),
    ).as_dict()

    return render(request, "orders/deliver.html", context)


@login_required
def detail(request, order_id: int):
    order = _get_order_or_404(order_id)

    active_panel = "order" if order.status == Order.Status.CANCELLED else "contents"

    context = build_order_detail_context(
        order=order,
        title=f"Order #{order.id}",
        description="",
        cancel_url=reverse("orders:index"),
        active_panel=active_panel,
        include_contents=True,
        primary_action=build_order_detail_primary_action(
            order=order,
            role_spec=request.role_spec,
        ),
        secondary_actions=build_order_secondary_actions(
            order=order,
            role_spec=request.role_spec,
        ),
    ).as_dict()

    return render(request, "orders/detail.html", context)


def _get_order_or_404(order_id: int) -> Order:
    return get_object_or_404(
        Order.objects
        .select_related(
            "customer",
            "edited_by",
            "placed_by",
            "packed_by",
            "delivered_by",
            "cancelled_by",
        )
        .prefetch_related("lines__product"),
        pk=order_id,
    )
