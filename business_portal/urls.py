from __future__ import annotations

from django.urls import path

from business_portal import views
from business_portal.catalog import views as catalog_views
from business_portal.orders import navbar_views
from business_portal.orders import repeat_views
from business_portal.orders import views as order_views
from business_portal.profile import views as profile_views


app_name = "business_portal"


urlpatterns = [
    path(
        "",
        views.index,
        name="index",
    ),
    path(
        "store/edit/",
        profile_views.edit_profile,
        name="edit_store",
    ),
    path(
        "orders/",
        order_views.orders,
        name="orders",
    ),
    path(
        "orders/<int:order_id>/",
        order_views.order_detail,
        name="order_detail",
    ),
    path(
        "orders/<int:order_id>/repeat/",
        repeat_views.repeat_order,
        name="repeat_order",
    ),
    path(
        "order/",
        order_views.current_order,
        name="current_order",
    ),
    path(
        "order/navbar-cart/",
        navbar_views.navbar_cart_fragment,
        name="navbar_cart_fragment",
    ),
    path(
        "order/review/",
        order_views.review_order,
        name="review_order",
    ),
    path(
        "order/lines/<int:order_line_id>/quantity/",
        order_views.set_draft_line_quantity,
        name="set_draft_line_quantity",
    ),
    path(
        "order/lines/<int:order_line_id>/remove/",
        order_views.remove_draft_line,
        name="remove_draft_line",
    ),
    path(
        "catalog/",
        catalog_views.catalog,
        name="catalog",
    ),
    path(
        "catalog/<int:product_id>/",
        catalog_views.product_detail,
        name="catalog_product",
    ),
    path(
        "catalog/<int:product_id>/add/",
        catalog_views.add_product,
        name="catalog_add_product",
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
]
