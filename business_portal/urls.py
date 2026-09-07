from __future__ import annotations

from django.urls import path

from business_portal import views
from business_portal.catalog import views as catalog_views
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
        "orders/",
        order_views.orders,
        name="orders",
    ),
    path(
        "order/",
        order_views.current_order,
        name="current_order",
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
        "orders/<int:order_id>/",
        order_views.order_detail,
        name="order_detail",
    ),
    path(
        "catalog/",
        catalog_views.catalog,
        name="catalog",
    ),
    path(
        "catalog/<int:product_id>/add/",
        catalog_views.add_product,
        name="catalog_add_product",
    ),
    path(
        "profile/",
        profile_views.profile,
        name="profile",
    ),
    path(
        "profile/edit/",
        profile_views.edit_profile,
        name="edit_profile",
    ),
    path(
        "contact/",
        views.contact,
        name="contact",
    ),
]
