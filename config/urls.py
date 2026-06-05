from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from dashboard import views as dashboard_views


urlpatterns = [
    path("", dashboard_views.index, name="index"), 
    path("admin/", admin.site.urls),

    # Django auth views:
    # /accounts/login/  -> name="login"
    # /accounts/logout/ -> name="logout"
    path("accounts/", include("django.contrib.auth.urls")),

    path("orders/", include("orders.urls", namespace="orders")),
    path("inventory/", include("inventory.urls", namespace="inventory")),
    path("products/", include("products.urls", namespace="products")),
    path("customers/", include("customers.urls", namespace="customers")),
]

# Serve uploaded files from Django in development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
