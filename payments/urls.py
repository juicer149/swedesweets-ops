from __future__ import annotations

from django.urls import path

from payments import views


app_name = "payments"


urlpatterns = [
    path(
        "sumup/webhook/",
        views.sumup_webhook,
        name="sumup_webhook",
    ),
]
