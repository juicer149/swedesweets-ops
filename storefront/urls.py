from django.urls import path

from storefront import views
from storefront.catalog import views as catalog_views


app_name = "storefront"


urlpatterns = [
    path(
        "",
        catalog_views.product_list,
        name="product_list",
    ),
    path(
        "products/<int:product_id>/",
        catalog_views.product_detail,
        name="product_detail",
    ),
    path(
        "cart/add/<int:product_id>/",
        catalog_views.add_to_cart,
        name="add_to_cart",
    ),
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
    path(
        "payment/<uuid:checkout_id>/return/",
        views.payment_return,
        name="payment_return",
    ),
]
