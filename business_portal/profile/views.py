from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from business_portal.profile.forms import (
    CustomerProfileForm,
    build_customer_profile_initial_data,
)
from business_portal.profile.services import (
    update_portal_customer_profile,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from customers.errors import InvalidCustomerData


@login_required
def profile(request):
    customer = get_portal_customer_for_user(
        user=request.user,
    )

    if request.method == "POST":
        form = CustomerProfileForm(
            request.POST,
            customer=customer,
        )

        if form.is_valid():
            try:
                update_portal_customer_profile(
                    customer=customer,
                    user=request.user,
                    **form.cleaned_data,
                )
            except InvalidCustomerData as error:
                form.add_error(
                    None,
                    str(error),
                )
            else:
                messages.success(
                    request,
                    _("Profile updated."),
                )
                return redirect(
                    "business_portal:profile"
                )

    else:
        form = CustomerProfileForm(
            initial=build_customer_profile_initial_data(
                customer
            ),
            customer=customer,
        )

    return render(
        request,
        "business_portal/profile.html",
        {
            "form": form,
            "customer": customer,
        },
    )


@login_required
def edit_profile(request):
    return redirect(
        "business_portal:profile"
    )
