from __future__ import annotations

from django.urls import path

from inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.index, name="index"),
    path("create/", views.create, name="create"),
    path("batches/<int:batch_pk>/", views.detail, name="detail"),
    path("batches/<int:batch_pk>/edit/", views.edit, name="edit"),
    path("batches/<int:batch_pk>/close/", views.close, name="close"),
]
