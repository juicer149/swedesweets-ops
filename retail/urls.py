from django.urls import path

from retail import views


app_name = "retail"


urlpatterns = [
    path(
        "payment/<uuid:checkout_id>/return/",
        views.payment_return,
        name="payment_return",
    ),
]
