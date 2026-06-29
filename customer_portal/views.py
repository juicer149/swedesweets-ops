from __future__ import annotations

from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
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
from customer_portal.form_viewmodels import (
    build_portal_place_order_context,
)
from customer_portal.forms import (
    PortalOrderLineFormSet,
    build_portal_order_line_initial_data,
    build_portal_order_line_inputs,
)
from customer_portal.order_list_viewmodels import (
    build_portal_order_page_rows,
    build_portal_orders_page_header,
)
from customer_portal.review_viewmodels import (
    build_portal_order_review_context,
)
from customer_portal.selectors import (
    get_portal_customer_for_user,
    get_portal_order_for_user,
)
from customer_portal.services import (
    DRAFT_CLEARED,
    DRAFT_SAVED,
    DRAFT_UNCHANGED,
    discard_portal_draft_order,
    save_or_clear_portal_draft_order,
)
from customer_portal.viewmodels import (
    RECENT_PORTAL_ORDER_LIMIT,
    build_portal_home_context,
)
from inventory.errors import InvalidStockOperation
from orders.errors import InvalidOrderOperation
from orders.models import Order
from orders.selectors import (
    CUSTOMER_ORDER_SORTS,
    DEFAULT_CUSTOMER_ORDER_SORT,
    get_active_draft_order_for_customer,
    get_customer_order_summary,
    list_customer_orders,
)
from orders.services import place_order as place_draft_order

PORTAL_ORDERS_LIST_ANCHOR = "portal-orders-list"
PORTAL_ORDER_FILTER_QUERY_KEY = "status"
ORDER_LINE_FORMSET_PREFIX = "lines"

ORDER_OPERATION_ERRORS = (
    InvalidOrderOperation,
    InvalidStockOperation,
)

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


@dataclass(frozen=True, slots=True)
class PortalDraftFormResult:
    line_formset: object
    draft_order: object | None
    form_errors: tuple[str, ...]
    succeeded: bool
    status: str


def _handle_portal_draft_form_post(
    *,
    request,
    customer,
    draft_order,
    require_lines: bool,
) -> PortalDraftFormResult:
    line_formset = PortalOrderLineFormSet(
        request.POST,
        prefix=ORDER_LINE_FORMSET_PREFIX,
        order=draft_order,
        require_lines=require_lines,
        language_code=request.LANGUAGE_CODE,
    )

    if not line_formset.is_valid():
        return PortalDraftFormResult(
            line_formset=line_formset,
            draft_order=draft_order,
            form_errors=(),
            succeeded=False,
            status=DRAFT_UNCHANGED,
        )

    line_inputs = build_portal_order_line_inputs(line_formset)

    result = save_or_clear_portal_draft_order(
        customer=customer,
        draft_order=draft_order,
        line_inputs=line_inputs,
        user=request.user,
    )

    return PortalDraftFormResult(
        line_formset=line_formset,
        draft_order=result.draft_order,
        form_errors=result.errors,
        succeeded=result.succeeded,
        status=result.status,
    )


def _add_service_errors(request, errors: tuple[str, ...]) -> None:
    for error in errors:
        messages.error(request, error)


def _add_draft_save_message(request, status: str) -> None:
    if status == DRAFT_SAVED:
        messages.success(
            request,
            _("Draft order saved."),
        )
        return

    if status == DRAFT_CLEARED:
        messages.success(
            request,
            _("Draft cleared."),
        )
        return

    if status == DRAFT_UNCHANGED:
        messages.info(
            request,
            _("Nothing to save."),
        )


@login_required
def index(request):
    customer = get_portal_customer_for_user(user=request.user)
    active_draft_order = get_active_draft_order_for_customer(customer=customer)

    context = build_portal_home_context(
        customer=customer,
        order_summary=get_customer_order_summary(customer=customer),
        recent_orders=tuple(
            list_customer_orders(customer=customer)[:RECENT_PORTAL_ORDER_LIMIT]
        ),
        active_draft_order=active_draft_order,
    ).as_dict()

    return render(request, "customer_portal/index.html", context)


@login_required
def orders(request):
    customer = get_portal_customer_for_user(user=request.user)
    active_draft_order = get_active_draft_order_for_customer(customer=customer)

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
        "page_header": build_portal_orders_page_header(
            active_draft_order=active_draft_order,
        ),
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
    customer = get_portal_customer_for_user(user=request.user)
    draft_order = get_active_draft_order_for_customer(customer=customer)
    form_errors: tuple[str, ...] = ()

    if request.method == "POST":
        intent = request.POST.get("intent", "review_order")

        if intent not in {
            "review_order",
            "save_draft",
            "discard_draft",
        }:
            messages.error(
                request,
                _("Unknown order action."),
            )
            return redirect("customer_portal:place_order")

        if intent == "discard_draft":
            result = discard_portal_draft_order(
                customer=customer,
                draft_order=draft_order,
            )

            if not result.succeeded:
                _add_service_errors(request, result.errors)
                return redirect("customer_portal:place_order")

            if result.status == DRAFT_CLEARED:
                messages.success(
                    request,
                    _("Draft order discarded."),
                )

            return redirect("accounts:after_login")

        if intent == "review_order":
            result = _handle_portal_draft_form_post(
                request=request,
                customer=customer,
                draft_order=draft_order,
                require_lines=True,
            )

            line_formset = result.line_formset
            draft_order = result.draft_order
            form_errors = result.form_errors

            if result.succeeded:
                return redirect("customer_portal:review_order")

        elif intent == "save_draft":
            result = _handle_portal_draft_form_post(
                request=request,
                customer=customer,
                draft_order=draft_order,
                require_lines=False,
            )

            line_formset = result.line_formset
            draft_order = result.draft_order
            form_errors = result.form_errors

            if result.succeeded:
                _add_draft_save_message(request, result.status)
                return redirect(_safe_next_url(request) or "accounts:after_login")

    else:
        initial = ()

        if draft_order is not None:
            initial = build_portal_order_line_initial_data(draft_order)

        line_formset = PortalOrderLineFormSet(
            initial=initial,
            prefix=ORDER_LINE_FORMSET_PREFIX,
            order=draft_order,
            language_code=request.LANGUAGE_CODE,
        )

    context = build_portal_place_order_context(
        line_formset=line_formset,
        form_errors=form_errors,
        has_active_draft=draft_order is not None,
    ).as_dict()

    return render(request, "customer_portal/place_order.html", context)


@login_required
def review_order(request):
    customer = get_portal_customer_for_user(user=request.user)
    draft_order = get_active_draft_order_for_customer(customer=customer)

    if draft_order is None:
        messages.info(
            request,
            _("No draft order to review."),
        )
        return redirect("customer_portal:place_order")

    if request.method == "POST":
        intent = request.POST.get("intent", "place_order")

        if intent not in {
            "place_order",
            "save_draft",
            "discard_draft",
        }:
            messages.error(
                request,
                _("Unknown order action."),
            )
            return redirect("customer_portal:review_order")

        if intent == "save_draft":
            # The review page has no editable line form. Reaching this page means
            # the draft has already been persisted by place_order.
            messages.success(
                request,
                _("Draft order saved."),
            )
            return redirect(_safe_next_url(request) or "accounts:after_login")

        if intent == "discard_draft":
            result = discard_portal_draft_order(
                customer=customer,
                draft_order=draft_order,
            )

            if not result.succeeded:
                _add_service_errors(request, result.errors)
                return redirect("customer_portal:review_order")

            if result.status == DRAFT_CLEARED:
                messages.success(
                    request,
                    _("Draft order discarded."),
                )

            return redirect("accounts:after_login")

        if intent == "place_order":
            try:
                placed_order = place_draft_order(
                    order=draft_order,
                    user=request.user,
                )
            except ORDER_OPERATION_ERRORS as error:
                messages.error(request, str(error))
                return redirect("customer_portal:review_order")

            messages.success(
                request,
                _("Order #%(order_id)s placed.")
                % {
                    "order_id": placed_order.id,
                },
            )
            return redirect(
                "customer_portal:order_detail",
                order_id=placed_order.id,
            )

    context = build_portal_order_review_context(
        order=draft_order,
        language_code=request.LANGUAGE_CODE,
    ).as_dict()

    return render(request, "customer_portal/review_order.html", context)


@login_required
def order_detail(request, order_id: int):
    order = get_portal_order_for_user(
        user=request.user,
        order_id=order_id,
    )

    context = build_portal_order_detail_context(
        order=order,
        language_code=request.LANGUAGE_CODE,
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


def _safe_next_url(request) -> str | None:
    next_url = request.POST.get("next", "").strip()
    if not next_url:
        return None

    if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return None
