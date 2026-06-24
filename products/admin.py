from django.contrib import admin

from products.models import ProductTranslation


@admin.register(ProductTranslation)
class ProductTranslationAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "language_code",
        "name",
    )
    list_filter = ("language_code",)
    search_fields = (
        "product__sku",
        "product__brand",
        "product__name",
        "name",
    )
