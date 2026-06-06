from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.list_viewmodels import (
    ACCOUNT_VIEW_CUSTOMER,
    ACCOUNT_VIEW_INTERNAL,
    ACCOUNT_VIEW_UNLINKED,
    build_account_page_rows,
    build_account_view_links,
    build_accounts_page_header,
)
from accounts.selectors import (
    list_customer_account_rows,
    list_internal_account_rows,
    list_unlinked_account_rows,
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
        "active_sort": controls.active_sort,
    }

    return render(request, "accounts/index.html", context)


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
