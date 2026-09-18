from __future__ import annotations

from uuid import UUID

from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse

from accounts.roles import AccountRole
from payments.models import PaymentAttempt
from retail.models import RetailCheckoutSession
from retail.payments import (
    RetailPaymentRecoveryAction,
    recover_retail_payment,
)


def _is_business_customer(
    request: HttpRequest,
) -> bool:
    return (
        getattr(
            request,
            "account_role",
            None,
        )
        == AccountRole.BUSINESS_CUSTOMER
    )


def landing(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "storefront/landing.html",
    )


def contact(request: HttpRequest) -> HttpResponse:
    if _is_business_customer(request):
        return redirect(
            "business_portal:contact"
        )

    return render(
        request,
        "storefront/contact.html",
    )


def faq(request: HttpRequest) -> HttpResponse:
    if _is_business_customer(request):
        return redirect(
            "business_portal:faq"
        )

    return render(
        request,
        "storefront/faq.html",
        {
            "contact_url": reverse(
                "public_site:contact"
            ),
        },
    )


def payment_return(
    request: HttpRequest,
    checkout_id: UUID,
) -> HttpResponse:
    """Recover a retail payment after the customer returns from SumUp.

    Provider redirects are not trusted as proof of payment.

    Recovery asks the provider for authoritative state when necessary and then
    maps the resulting application state to the next customer-facing action.
    """

    checkout = get_object_or_404(
        RetailCheckoutSession.objects.select_related(
            "order",
        ),
        pk=checkout_id,
    )

    attempt = (
        PaymentAttempt.objects
        .filter(
            order=checkout.order,
        )
        .first()
    )

    if attempt is None:
        raise Http404(
            "No payment attempt exists for this checkout."
        )

    recovery = recover_retail_payment(
        attempt=attempt,
    )

    if (
        recovery.action
        == RetailPaymentRecoveryAction.CONTINUE_PAYMENT
    ):
        if recovery.redirect_url is None:
            return HttpResponse(
                "Payment requires support.",
                status=200,
            )

        return HttpResponseRedirect(
            recovery.redirect_url
        )

    if (
        recovery.action
        == RetailPaymentRecoveryAction.CONFIRMED
    ):
        return HttpResponse(
            "Payment confirmed.",
            status=200,
        )

    if (
        recovery.action
        == RetailPaymentRecoveryAction.PAYMENT_FAILED
    ):
        return HttpResponse(
            "Payment failed.",
            status=200,
        )

    return HttpResponse(
        "Payment requires support.",
        status=200,
    )
