from __future__ import annotations

from django.urls import path

from orders import views


app_name = "orders"

urlpatterns = [
    path("", views.index, name="index"),
    path("create/", views.create, name="create"),
    path("<int:order_id>/", views.detail, name="detail"),
    path("<int:order_id>/edit/", views.edit, name="edit"),
    path("<int:order_id>/cancel/", views.cancel, name="cancel"),
    path("<int:order_id>/pack/", views.pack, name="pack"),
    path("<int:order_id>/deliver/", views.deliver, name="deliver"),
]
