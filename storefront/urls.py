from django.urls import path

from storefront import views


app_name = "storefront"


urlpatterns = [
    path(
        "payment/<uuid:checkout_id>/return/",
        views.payment_return,
        name="payment_return",
    ),
]
