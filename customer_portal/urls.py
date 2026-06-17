from __future__ import annotations

from django.urls import path

from customer_portal import views


app_name = "customer_portal"


urlpatterns = [
    path("", views.index, name="index"),
    path("orders/", views.orders, name="orders"),
    path("orders/place/", views.place_order, name="place_order"),
    path("orders/review/", views.review_order, name="review_order"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("catalog/", views.catalog, name="catalog"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("contact/", views.contact, name="contact"),
]
