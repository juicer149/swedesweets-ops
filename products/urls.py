from __future__ import annotations

from django.urls import path

from products import views


app_name = "products"

urlpatterns = [
    path("", views.index, name="index"),
    path("create/", views.create, name="create"),
    path("<int:product_pk>/", views.detail, name="detail"),
    path("<int:product_pk>/edit/", views.edit, name="edit"),
]
