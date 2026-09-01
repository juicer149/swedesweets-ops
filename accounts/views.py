from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.access import get_after_login_redirect_name
from accounts.self_viewmodels import build_self_account_detail_context
from accounts.selectors import (
    get_account_record,
    list_account_activities,
)


def inactive(request):
    return render(
        request,
        "accounts/inactive.html",
    )


@login_required
def after_login(request):
    return redirect(
        get_after_login_redirect_name(
            account_role=request.account_role,
            role_spec=request.role_spec,
        )
    )


@login_required
def me(request):
    account = get_account_record(
        user=request.user
    )
    activities = list_account_activities(
        user=request.user
    )

    context = build_self_account_detail_context(
        account=account,
        activity_rows=activities,
        cancel_url=reverse("accounts:after_login"),
        role_spec=request.role_spec,
    ).as_dict()

    return render(
        request,
        "accounts/detail.html",
        context,
    )
