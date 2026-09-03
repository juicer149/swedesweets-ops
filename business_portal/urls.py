from __future__ import annotations

from django.urls import path

from business_portal import views
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
        "orders/place/",
        order_views.place_order,
        name="place_order",
    ),
    path(
        "orders/review/",
        order_views.review_order,
        name="review_order",
    ),
    path(
        "orders/<int:order_id>/",
        order_views.order_detail,
        name="order_detail",
    ),
    path(
        "catalog/",
        views.catalog,
        name="catalog",
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
