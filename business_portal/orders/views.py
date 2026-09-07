from __future__ import annotations

from enum import StrEnum

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from business.services import (
    place_order as place_draft_order,
    remove_product_from_draft_order,
    set_draft_product_quantity,
)
from business_portal.orders.detail_viewmodels import (
    build_portal_order_detail_context,
)
from business_portal.orders.form_viewmodels import (
    build_portal_current_order_context,
)
from business_portal.orders.list_viewmodels import (
    build_portal_order_page_rows,
    build_portal_orders_page_header,
)
from business_portal.orders.review_viewmodels import (
    build_portal_order_review_context,
)
from business_portal.orders.selectors import (
    get_portal_order_for_user,
)
from business_portal.orders.services import (
    DraftStatus,
    discard_portal_draft_order,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from common.table_controls import (
    TableControls,
    TableControlsTemplate,
    TableFilter,
    TableSortField,
)
from inventory.errors import InvalidStockOperation
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from orders.selectors import (
    CUSTOMER_ORDER_SORTS,
    DEFAULT_CUSTOMER_ORDER_SORT,
    get_active_draft_order_for_customer,
    list_customer_orders,
)


class PortalOrderIntent(StrEnum):
    REVIEW_ORDER = "review_order"
    PLACE_ORDER = "place_order"
    SAVE_DRAFT = "save_draft"
    DISCARD_DRAFT = "discard_draft"


PORTAL_ORDERS_LIST_ANCHOR = "portal-orders-list"
PORTAL_ORDER_FILTER_QUERY_KEY = "status"

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


def _add_service_errors(
    request,
    errors: tuple[str, ...],
) -> None:
    for error in errors:
        messages.error(
            request,
            error,
        )


def _get_portal_draft_line(
    *,
    user,
    order_line_id: int,
) -> OrderLine:
    customer = get_portal_customer_for_user(
        user=user,
    )

    return get_object_or_404(
        OrderLine.objects.select_related(
            "order",
            "product",
        ),
        pk=order_line_id,
        order__channel=Order.Channel.BUSINESS,
        order__customer=customer,
        order__status=Order.Status.DRAFT,
    )


@login_required
@require_POST
def set_draft_line_quantity(
    request,
    order_line_id: int,
):
    line = _get_portal_draft_line(
        user=request.user,
        order_line_id=order_line_id,
    )

    raw_quantity = request.POST.get(
        "quantity",
        "",
    ).strip()

    try:
        quantity = int(
            raw_quantity
        )
    except ValueError:
        messages.error(
            request,
            _("Quantity must be a whole number."),
        )
        return redirect(
            "business_portal:current_order"
        )

    try:
        set_draft_product_quantity(
            order=line.order,
            product=line.product,
            quantity=quantity,
            user=request.user,
        )
    except ORDER_OPERATION_ERRORS as error:
        messages.error(
            request,
            str(error),
        )
    else:
        messages.success(
            request,
            _("Quantity updated."),
        )

    return redirect(
        "business_portal:current_order"
    )


@login_required
@require_POST
def remove_draft_line(
    request,
    order_line_id: int,
):
    line = _get_portal_draft_line(
        user=request.user,
        order_line_id=order_line_id,
    )

    try:
        remove_product_from_draft_order(
            order=line.order,
            product=line.product,
            user=request.user,
        )
    except ORDER_OPERATION_ERRORS as error:
        messages.error(
            request,
            str(error),
        )
    else:
        messages.success(
            request,
            _("Product removed from your order."),
        )

    return redirect(
        "business_portal:current_order"
    )


@login_required
def orders(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    active_draft_order = get_active_draft_order_for_customer(
        customer=customer,
    )

    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=PORTAL_ORDERS_LIST_ANCHOR,
        requested_filter=request.GET.get(
            PORTAL_ORDER_FILTER_QUERY_KEY,
            "",
        ),
        requested_sort=request.GET.get(
            "sort",
            "",
        ),
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
        "filters": controls.build_filter_links(
            PORTAL_ORDER_FILTERS
        ),
        "table_sorts": controls.build_table_sort_links(
            PORTAL_ORDER_TABLE_SORTS
        ),
        "mobile_sort_fields": controls.build_mobile_sort_fields(
            PORTAL_ORDER_TABLE_SORTS
        ),
        "mobile_sort_direction": (
            controls.build_mobile_sort_direction()
        ),
        "table_controls_template": (
            PORTAL_ORDER_TABLE_CONTROLS_TEMPLATE
        ),
        "numeric_table_fields": [
            "quantity",
        ],
    }

    return render(
        request,
        "business_portal/orders/index.html",
        context,
    )


@login_required
def current_order(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    draft_order = get_active_draft_order_for_customer(
        customer=customer,
    )

    if request.method == "POST":
        try:
            intent = PortalOrderIntent(
                request.POST.get(
                    "intent",
                    PortalOrderIntent.REVIEW_ORDER,
                )
            )
        except ValueError:
            messages.error(
                request,
                _("Unknown order action."),
            )
            return redirect(
                "business_portal:current_order"
            )

        match intent:
            case PortalOrderIntent.DISCARD_DRAFT:
                result = discard_portal_draft_order(
                    customer=customer,
                    draft_order=draft_order,
                )

                if not result.succeeded:
                    _add_service_errors(
                        request,
                        result.errors,
                    )
                    return redirect(
                        "business_portal:current_order"
                    )

                if result.status == DraftStatus.CLEARED:
                    messages.success(
                        request,
                        _("Draft order discarded."),
                    )

                return redirect(
                    "accounts:after_login"
                )

            case PortalOrderIntent.REVIEW_ORDER:
                if (
                    draft_order is None
                    or not draft_order.lines.exists()
                ):
                    messages.error(
                        request,
                        _("Add at least one product."),
                    )
                    return redirect(
                        "business_portal:current_order"
                    )

                return redirect(
                    "business_portal:review_order"
                )

            case PortalOrderIntent.SAVE_DRAFT:
                if draft_order is None:
                    messages.info(
                        request,
                        _("No draft order to save."),
                    )
                else:
                    messages.success(
                        request,
                        _("Draft order saved."),
                    )

                return redirect(
                    _safe_next_url(request)
                    or "accounts:after_login"
                )

            case _:
                messages.error(
                    request,
                    _("Unknown order action."),
                )
                return redirect(
                    "business_portal:current_order"
                )

    context = build_portal_current_order_context(
        draft_order=draft_order,
        language_code=request.LANGUAGE_CODE,
    ).as_dict()

    return render(
        request,
        "business_portal/orders/current.html",
        context,
    )


@login_required
def review_order(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    draft_order = get_active_draft_order_for_customer(
        customer=customer,
    )

    if draft_order is None:
        messages.info(
            request,
            _("No draft order to review."),
        )
        return redirect(
            "business_portal:current_order"
        )

    if request.method == "POST":
        try:
            intent = PortalOrderIntent(
                request.POST.get(
                    "intent",
                    PortalOrderIntent.PLACE_ORDER,
                )
            )
        except ValueError:
            messages.error(
                request,
                _("Unknown order action."),
            )
            return redirect(
                "business_portal:review_order"
            )

        match intent:
            case PortalOrderIntent.SAVE_DRAFT:
                messages.success(
                    request,
                    _("Draft order saved."),
                )
                return redirect(
                    _safe_next_url(request)
                    or "accounts:after_login"
                )

            case PortalOrderIntent.DISCARD_DRAFT:
                result = discard_portal_draft_order(
                    customer=customer,
                    draft_order=draft_order,
                )

                if not result.succeeded:
                    _add_service_errors(
                        request,
                        result.errors,
                    )
                    return redirect(
                        "business_portal:review_order"
                    )

                if result.status == DraftStatus.CLEARED:
                    messages.success(
                        request,
                        _("Draft order discarded."),
                    )

                return redirect(
                    "accounts:after_login"
                )

            case PortalOrderIntent.PLACE_ORDER:
                try:
                    placed_order = place_draft_order(
                        order=draft_order,
                        user=request.user,
                    )
                except ORDER_OPERATION_ERRORS as error:
                    messages.error(
                        request,
                        str(error),
                    )
                    return redirect(
                        "business_portal:review_order"
                    )

                messages.success(
                    request,
                    _(
                        "Order #%(order_id)s placed."
                    )
                    % {
                        "order_id": placed_order.id,
                    },
                )

                return redirect(
                    "business_portal:order_detail",
                    order_id=placed_order.id,
                )

            case _:
                messages.error(
                    request,
                    _("Unknown order action."),
                )
                return redirect(
                    "business_portal:review_order"
                )

    context = build_portal_order_review_context(
        order=draft_order,
        language_code=request.LANGUAGE_CODE,
    ).as_dict()

    return render(
        request,
        "business_portal/orders/review.html",
        context,
    )


@login_required
def order_detail(
    request,
    order_id: int,
):
    order = get_portal_order_for_user(
        user=request.user,
        order_id=order_id,
    )

    context = build_portal_order_detail_context(
        order=order,
        language_code=request.LANGUAGE_CODE,
    ).as_dict()

    return render(
        request,
        "business_portal/orders/detail.html",
        context,
    )


def _safe_next_url(
    request,
) -> str | None:
    next_url = request.POST.get(
        "next",
        "",
    ).strip()

    if not next_url:
        return None

    if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={
            request.get_host(),
        },
        require_https=request.is_secure(),
    ):
        return next_url

    return None
