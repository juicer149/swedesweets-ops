from __future__ import annotations

from enum import StrEnum

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from business.services import (
    place_order as place_draft_order,
    remove_draft_line as remove_business_draft_line,
    set_draft_line_quantity as set_business_draft_line_quantity,
)
from business_portal.orders.detail_viewmodels import (
    build_portal_order_detail_context,
)
from business_portal.orders.form_viewmodels import (
    build_portal_current_order_context,
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
from inventory.errors import InvalidStockOperation
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from orders.selectors import (
    get_active_draft_order_for_customer,
)


class PortalOrderIntent(StrEnum):
    REVIEW_ORDER = "review_order"
    PLACE_ORDER = "place_order"
    DISCARD_DRAFT = "discard_draft"


ORDER_OPERATION_ERRORS = (
    InvalidOrderOperation,
    InvalidStockOperation,
)


def _wants_json(
    request,
) -> bool:
    return (
        "application/json"
        in request.headers.get(
            "Accept",
            "",
        )
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

    wants_json = _wants_json(
        request
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
        message = _(
            "Quantity must be a whole number."
        )

        if wants_json:
            return JsonResponse(
                {
                    "ok": False,
                    "message": str(message),
                },
                status=400,
            )

        messages.error(
            request,
            message,
        )

        return redirect(
            "business_portal:current_order"
        )

    try:
        set_business_draft_line_quantity(
            order=line.order,
            order_line_id=line.id,
            quantity=quantity,
            user=request.user,
        )
    except ORDER_OPERATION_ERRORS as error:
        message = str(error)

        if wants_json:
            return JsonResponse(
                {
                    "ok": False,
                    "message": message,
                },
                status=400,
            )

        messages.error(
            request,
            message,
        )
    else:
        message = _(
            "Quantity updated."
        )

        if wants_json:
            return JsonResponse(
                {
                    "ok": True,
                    "message": str(message),
                    "quantity": quantity,
                }
            )

        messages.success(
            request,
            message,
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

    wants_json = _wants_json(
        request
    )

    try:
        remove_business_draft_line(
            order=line.order,
            order_line_id=line.id,
            user=request.user,
        )
    except ORDER_OPERATION_ERRORS as error:
        message = str(error)

        if wants_json:
            return JsonResponse(
                {
                    "ok": False,
                    "message": message,
                },
                status=400,
            )

        messages.error(
            request,
            message,
        )
    else:
        message = _(
            "Product removed from your order."
        )

        if wants_json:
            return JsonResponse(
                {
                    "ok": True,
                    "message": str(message),
                    "order_line_id": line.id,
                }
            )

        messages.success(
            request,
            message,
        )

    return redirect(
        "business_portal:current_order"
    )


@login_required
@require_GET
def orders(request):
    target = reverse(
        "business_portal:index"
    )

    query_params = request.GET.copy()
    query_params["tab"] = "orders"

    query_string = query_params.urlencode()

    if query_string:
        target = (
            f"{target}?{query_string}"
        )

    return redirect(target)


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
