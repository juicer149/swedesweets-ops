from __future__ import annotations

from django.contrib import admin

from customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "phone_number",
        "city",
        "country",
    )
    list_filter = ("country", "city")
    search_fields = (
        "name",
        "email",
        "phone_number",
        "city",
        "address_line",
    )
    ordering = ("name", "email")
