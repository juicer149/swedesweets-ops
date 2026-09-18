from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import (
    include,
    path,
)

from ops_portal.dashboard import views as dashboard_views
from storefront import views as storefront_views


urlpatterns = [
    path(
        "i18n/",
        include("django.conf.urls.i18n"),
    ),
    path(
        "",
        storefront_views.landing,
        name="index",
    ),
    path(
        "",
        include(
            "storefront.public_urls",
            namespace="public_site",
        ),
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
        include("django.contrib.auth.urls"),
    ),
    path(
        "ops/",
        dashboard_views.index,
        name="ops_dashboard",
    ),
    path(
        "ops/accounts/",
        include(
            "ops_portal.accounts.urls",
            namespace="ops_accounts",
        ),
    ),
    path(
        "ops/orders/",
        include(
            "ops_portal.orders.urls",
            namespace="ops_orders",
        ),
    ),
    path(
        "ops/inventory/",
        include(
            "ops_portal.inventory.urls",
            namespace="ops_inventory",
        ),
    ),
    path(
        "ops/products/",
        include(
            "ops_portal.products.urls",
            namespace="ops_products",
        ),
    ),
    path(
        "ops/customers/",
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


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
