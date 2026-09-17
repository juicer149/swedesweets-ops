from django.urls import path

from storefront import views


app_name = "public_site"


urlpatterns = [
    path(
        "contact/",
        views.contact,
        name="contact",
    ),
    path(
        "faq/",
        views.faq,
        name="faq",
    ),
]
