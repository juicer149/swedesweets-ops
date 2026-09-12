from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.translation import (
    gettext as _,
    ngettext,
)
from django.views.decorators.http import require_POST

from business_portal.orders.repeat_services import (
    RepeatOrderSkipReason,
    repeat_order_into_draft,
)
from business_portal.orders.selectors import (
    get_portal_order_for_user,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from products.localization import translated_product_name


@login_required
@require_POST
def repeat_order(
    request,
    order_id: int,
):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    source_order = get_portal_order_for_user(
        user=request.user,
        order_id=order_id,
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
        user=request.user,
    )

    if result.added_count:
        messages.success(
            request,
            ngettext(
                "%(count)s order item was added to your current order.",
                "%(count)s order items were added to your current order.",
                result.added_count,
            )
            % {
                "count": result.added_count,
            },
        )

    for skipped in result.skipped:
        product_name = translated_product_name(
            skipped.product,
            language_code=request.LANGUAGE_CODE,
        )

        messages.warning(
            request,
            _skip_message(
                product_name=product_name,
                quantity=skipped.quantity,
                reason=skipped.reason,
            ),
        )

    if result.has_added_lines:
        return redirect(
            "business_portal:current_order"
        )

    return redirect(
        "business_portal:order_detail",
        order_id=source_order.id,
    )


def _skip_message(
    *,
    product_name: str,
    quantity: int,
    reason: RepeatOrderSkipReason,
) -> str:
    match reason:
        case RepeatOrderSkipReason.PRODUCT_UNAVAILABLE:
            return _(
                "%(product)s is no longer available for business ordering."
            ) % {
                "product": product_name,
            }

        case RepeatOrderSkipReason.OFFER_UNAVAILABLE:
            return _(
                "%(product)s was not added because the original offer "
                "is no longer available."
            ) % {
                "product": product_name,
            }

        case RepeatOrderSkipReason.QUANTITY_UNAVAILABLE:
            return _(
                "%(product)s was not added because %(quantity)s units "
                "are not currently available."
            ) % {
                "product": product_name,
                "quantity": quantity,
            }

        case _:
            return _(
                "%(product)s could not be added to your current order."
            ) % {
                "product": product_name,
            }
