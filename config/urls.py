from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import (
    include,
    path,
)

from ops_portal.dashboard import views as dashboard_views


urlpatterns = [
    path(
        "i18n/",
        include("django.conf.urls.i18n"),
    ),
    path(
        "",
        dashboard_views.index,
        name="index",
    ),
    path(
        "admin/",
        admin.site.urls,
    ),
    path(
        "accounts/",
        include(
            "accounts.urls",
            namespace="accounts",
        ),
    ),
    path(
        "accounts/",
        include(
            "ops_portal.accounts.urls",
            namespace="ops_accounts",
        ),
    ),
    # Django auth views:
    # /accounts/login/  -> name="login"
    # /accounts/logout/ -> name="logout"
    path(
        "accounts/",
        include("django.contrib.auth.urls"),
    ),
    path(
        "orders/",
        include(
            "orders.urls",
            namespace="orders",
        ),
    ),
    path(
        "inventory/",
        include(
            "ops_portal.inventory.urls",
            namespace="ops_inventory",
        ),
    ),
    path(
        "products/",
        include(
            "ops_portal.products.urls",
            namespace="ops_products",
        ),
    ),
    path(
        "customers/",
        include(
            "ops_portal.customers.urls",
            namespace="ops_customers",
        ),
    ),
    path(
        "my/",
        include(
            "business_portal.urls",
            namespace="business_portal",
        ),
    ),
    path(
        "payments/",
        include(
            "payments.urls",
            namespace="payments",
        ),
    ),
    path(
        "shop/",
        include(
            "storefront.urls",
            namespace="storefront",
        ),
    ),
]


# Serve uploaded files from Django in development.
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
