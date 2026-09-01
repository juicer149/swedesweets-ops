from __future__ import annotations

from django.urls import path

from ops_portal.accounts import views


app_name = "ops_accounts"


urlpatterns = [
    path(
        "",
        views.index,
        name="index",
    ),
    path(
        "internal/create/",
        views.create_internal,
        name="create_internal",
    ),
    path(
        "internal/<int:user_id>/edit/",
        views.edit_internal,
        name="edit_internal",
    ),
    path(
        "customer/create/",
        views.create_customer_account,
        name="create_customer_account",
    ),
    path(
        "customer/<int:user_id>/activate/",
        views.activate_customer_account,
        name="activate_customer_account",
    ),
    path(
        "customer/<int:user_id>/deactivate/",
        views.deactivate_customer_account,
        name="deactivate_customer_account",
    ),
    path(
        "<int:user_id>/",
        views.detail,
        name="detail",
    ),
]
