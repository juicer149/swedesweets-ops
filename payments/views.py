from __future__ import annotations

import json
import logging

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
)
from django.views.decorators.csrf import csrf_exempt

from payments.models import PaymentAttempt
from retail.payments import (
    PaymentReconciliationConflict,
    reconcile_retail_payment,
)


logger = logging.getLogger(__name__)


SUMUP_CHECKOUT_STATUS_CHANGED = "CHECKOUT_STATUS_CHANGED"


@csrf_exempt
def sumup_webhook(
    request: HttpRequest,
) -> HttpResponse:
    """Receive and reconcile SumUp checkout status notifications.

    The webhook body is only a notification.

    Provider state is verified through the SumUp API by
    reconcile_retail_payment() before local payment state changes.

    Reconciliation failures return a server error so the provider can retry
    the notification instead of treating an unresolved payment as handled.
    """

    if request.method != "POST":
        return HttpResponseNotAllowed(
            permitted_methods=[
                "POST",
            ]
        )

    try:
        payload = json.loads(
            request.body
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return HttpResponseBadRequest(
            "Invalid JSON."
        )

    if not isinstance(
        payload,
        dict,
    ):
        return HttpResponseBadRequest(
            "Webhook payload must be a JSON object."
        )

    event_type = payload.get(
        "event_type"
    )

    if event_type != SUMUP_CHECKOUT_STATUS_CHANGED:
        return HttpResponse(
            status=204
        )

    provider_payment_id = payload.get(
        "id"
    )

    if (
        not isinstance(
            provider_payment_id,
            str,
        )
        or not provider_payment_id.strip()
    ):
        return HttpResponseBadRequest(
            "Checkout id is required."
        )

    provider_payment_id = (
        provider_payment_id.strip()
    )

    try:
        attempt = PaymentAttempt.objects.get(
            provider=PaymentAttempt.Provider.SUMUP,
            provider_payment_id=provider_payment_id,
        )
    except PaymentAttempt.DoesNotExist:
        logger.info(
            "Ignoring SumUp webhook for unknown checkout %s",
            provider_payment_id,
        )

        return HttpResponse(
            status=204
        )

    try:
        reconcile_retail_payment(
            attempt=attempt,
        )
    except PaymentReconciliationConflict:
        logger.exception(
            "SumUp payment reconciliation conflict for attempt %s",
            attempt.pk,
        )

        return HttpResponse(
            status=500
        )
    except Exception:
        logger.exception(
            "SumUp payment reconciliation failed for attempt %s",
            attempt.pk,
        )

        return HttpResponse(
            status=500
        )

    return HttpResponse(
        status=204
    )
