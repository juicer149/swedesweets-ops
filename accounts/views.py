from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.access import get_after_login_redirect_name
from accounts.detail_viewmodels import (
    build_account_detail_context,
    build_self_account_detail_context,
)
from accounts.errors import AccountCreationError
from accounts.form_viewmodels import (
    build_create_customer_account_form_context,
    build_create_internal_account_form_context,
    build_edit_internal_account_form_context,
)
from accounts.forms import (
    CustomerAccountCreateForm,
    InternalAccountCreateForm, 
    InternalAccountEditForm,
)
from accounts.list_viewmodels import (
    ACCOUNT_VIEW_CUSTOMER,
    ACCOUNT_VIEW_INTERNAL,
    ACCOUNT_VIEW_UNLINKED,
    build_account_page_rows,
    build_account_view_links,
    build_accounts_page_header,
)
from accounts.models import StaffAccount
from accounts.selectors import (
    get_account_row,
    get_account_user,
    list_account_activity_rows,
    list_customer_account_rows,
    list_internal_account_rows,
    list_unlinked_account_rows,
)
from accounts.services import (
    create_customer_account as create_customer_login_account,
    create_internal_account, 
    update_internal_account,
)
from common.table_controls import (
    TableControls,
    TableControlsTemplate,
    TableSortField,
)


ACCOUNT_DEFAULT_VIEW = ACCOUNT_VIEW_INTERNAL
ACCOUNT_ALLOWED_VIEWS = {
    ACCOUNT_VIEW_INTERNAL,
    ACCOUNT_VIEW_CUSTOMER,
    ACCOUNT_VIEW_UNLINKED,
}

ACCOUNT_LIST_ANCHOR = "accounts-list"
ACCOUNT_VIEW_QUERY_KEY = "view"

#TODO: flytta till selectors eller services, och använd i list_account_rows
ACCOUNT_SORTS = {
    "account": ("email", "username"),
    "-account": ("-email", "-username"),
    "role": ("role", "email"),
    "-role": ("-role", "email"),
    "linked": ("linked", "email"),
    "-linked": ("-linked", "email"),
    "status": ("status", "email"),
    "-status": ("-status", "email"),
    "last_login": ("last_login", "email"),
    "-last_login": ("-last_login", "email"),
    "joined": ("date_joined", "email"),
    "-joined": ("-date_joined", "email"),
}

ACCOUNT_DEFAULT_SORT = "account"

ACCOUNT_TABLE_SORTS = [
    TableSortField("account", "Account"),
    TableSortField("role", "Role"),
    TableSortField("linked", "Linked identity"),
    TableSortField("status", "Status"),
    TableSortField("last_login", "Last login"),
    TableSortField("joined", "Joined"),
]

ACCOUNT_TABLE_CONTROLS_TEMPLATE = TableControlsTemplate(
    filters_title_id="accounts-filters-title",
    filters_aria_label="Account filters",
    sort_title_id="accounts-sort-title",
    sort_select_id="mobile-account-sort",
)


def inactive(request):
    return render(request, "accounts/inactive.html")


@login_required
def after_login(request):
    return redirect(
        get_after_login_redirect_name(
            account_role=request.account_role,
            role_spec=request.role_spec,
        )
    )


@login_required
def index(request):
    active_view = _active_account_view(
        request.GET.get(ACCOUNT_VIEW_QUERY_KEY, "")
    )

    controls = TableControls.from_request_values(
        base_path=request.path,
        anchor=ACCOUNT_LIST_ANCHOR,
        requested_filter="",
        requested_sort=request.GET.get("sort", ""),
        filters=[],
        allowed_sorts=ACCOUNT_SORTS,
        default_sort=ACCOUNT_DEFAULT_SORT,
        extra_query_params={
            ACCOUNT_VIEW_QUERY_KEY: active_view,
        },
    )

    account_rows = _list_account_rows(
        active_view=active_view,
        sort=controls.active_sort,
    )

    context = {
        "page_header": build_accounts_page_header(active_view=active_view),
        "view_links": build_account_view_links(active_view=active_view),
        "account_rows": build_account_page_rows(account_rows),
        "filters": [],
        "table_sorts": controls.build_table_sort_links(ACCOUNT_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(
            ACCOUNT_TABLE_SORTS
        ),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": ACCOUNT_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": [],
        "active_view": active_view,
    }

    return render(request, "accounts/index.html", context)


@login_required
def me(request):
    account = get_account_row(user=request.user)
    activity_rows = list_account_activity_rows(user=request.user)

    context = build_self_account_detail_context(
        account=account,
        activity_rows=activity_rows,
        cancel_url=reverse("index"),
    ).as_dict()

    return render(request, "accounts/detail.html", context)


@login_required
def detail(request, user_id: int):
    account_user = get_account_user(user_id=user_id)
    account = get_account_row(user=account_user)
    activity_rows = list_account_activity_rows(user=account_user)

    context = build_account_detail_context(
        account=account,
        activity_rows=activity_rows,
        cancel_url=_accounts_internal_url(),
        edit_url=_internal_account_edit_url(account_user),
    ).as_dict()

    return render(request, "accounts/detail.html", context)


@login_required
def create_internal(request):
    if request.method == "POST":
        form = InternalAccountCreateForm(request.POST)

        if form.is_valid():
            try:
                result = create_internal_account(
                    email=form.cleaned_data["email"],
                    access_level=form.cleaned_data["access_level"],
                    password=form.cleaned_data["password1"],
                )
            except AccountCreationError as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Internal account {result.user.email} created.",
                )
                return redirect(_accounts_internal_url())
    else:
        form = InternalAccountCreateForm()

    context = build_create_internal_account_form_context(
        form=form,
    ).as_dict()

    return render(request, "accounts/account_form.html", context)


@login_required
def edit_internal(request, user_id: int):
    staff_account = get_object_or_404(
        StaffAccount.objects.select_related("user"),
        user_id=user_id,
    )
    account_user = staff_account.user

    if request.method == "POST":
        form = InternalAccountEditForm(request.POST)

        if form.is_valid():
            try:
                update_internal_account(
                    user=account_user,
                    email=form.cleaned_data["email"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    access_level=form.cleaned_data["access_level"],
                    is_active=form.cleaned_data["is_active"],
                    actor=request.user,
                )
            except AccountCreationError as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Internal account {form.cleaned_data['email']} updated.",
                )
                return redirect(
                    "accounts:detail",
                    user_id=account_user.pk,
                )
    else:
        form = InternalAccountEditForm(
            initial=_internal_account_edit_initial(staff_account)
        )

    context = build_edit_internal_account_form_context(
        form=form,
        user_id=account_user.pk,
    ).as_dict()

    return render(request, "accounts/account_form.html", context)


@login_required
def create_customer_account(request):
    if request.method == "POST":
        form = CustomerAccountCreateForm(request.POST)

        if form.is_valid():
            try:
                result = create_customer_login_account(
                    email=form.cleaned_data["email"],
                    customer=form.cleaned_data["customer"],
                    password=form.cleaned_data["password1"],
                )
            except AccountCreationError as error:
                form.add_error(None, str(error))
            else:
                messages.success(
                    request,
                    f"Customer account {result.user.email} created.",
                )
                return redirect(_accounts_customer_url())
    else:
        form = CustomerAccountCreateForm()

    context = build_create_customer_account_form_context(
        form=form,
    ).as_dict()

    return render(request, "accounts/account_form.html", context)


def _list_account_rows(
    *,
    active_view: str,
    sort: str,
):
    if active_view == ACCOUNT_VIEW_CUSTOMER:
        return list_customer_account_rows(sort=sort)

    if active_view == ACCOUNT_VIEW_UNLINKED:
        return list_unlinked_account_rows(sort=sort)

    return list_internal_account_rows(sort=sort)


def _active_account_view(value: str) -> str:
    if value in ACCOUNT_ALLOWED_VIEWS:
        return value

    return ACCOUNT_DEFAULT_VIEW


def _internal_account_edit_initial(staff_account: StaffAccount) -> dict:
    user = staff_account.user

    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "access_level": staff_account.access_level,
        "is_active": user.is_active,
    }


def _internal_account_edit_url(user) -> str:
    if not hasattr(user, "staff_account"):
        return ""

    return reverse(
        "accounts:edit_internal",
        kwargs={"user_id": user.pk},
    )


def _accounts_internal_url() -> str:
    return (
        f"{reverse('accounts:index')}"
        f"?view={ACCOUNT_VIEW_INTERNAL}#accounts-list"
    )


def _accounts_customer_url() -> str:
    return (
        f"{reverse('accounts:index')}"
        f"?view={ACCOUNT_VIEW_CUSTOMER}#accounts-list"
    )
