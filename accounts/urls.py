from __future__ import annotations

from django.urls import path

from accounts import views


app_name = "accounts"

urlpatterns = [
    path("", views.index, name="index"),
    path("me/", views.me, name="me"),
    path("inactive/", views.inactive, name="inactive"),
    path("internal/create/", views.create_internal, name="create_internal"),
    path(
        "internal/<int:user_id>/edit/",
        views.edit_internal,
        name="edit_internal",
    ),
    path("<int:user_id>/", views.detail, name="detail"),
]
