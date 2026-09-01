from __future__ import annotations

from django.shortcuts import render

from ops_portal.dashboard.actions import build_dashboard_actions
from ops_portal.dashboard.queues import build_dashboard_queue_context


def index(request):
    dashboard_actions = build_dashboard_actions(
        account_role=request.account_role,
        role_spec=request.role_spec,
    )
    queue_context = build_dashboard_queue_context(
        account_role=request.account_role,
        role_spec=request.role_spec,
        requested_queue=request.GET.get("queue", ""),
    )

    return render(
        request,
        "ops_portal/dashboard/index.html",
        {
            "dashboard_actions": dashboard_actions,
            "dashboard_queue_tabs": queue_context.tabs,
            "dashboard_queue_panel": queue_context.panel,
        },
    )
