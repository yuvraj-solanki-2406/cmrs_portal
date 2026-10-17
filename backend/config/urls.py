from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from apps.common.views import not_found as api_not_found
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


handler404 = "apps.common.views.not_found"
handler500 = "apps.common.views.server_error"


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.lending.urls")),
    path("api/v1/", include("apps.collections.urls")),
    path("api/v1/", include("apps.cash.urls")),
    path("api/v1/", include("apps.treasury.urls")),
    path("api/v1/", include("apps.reporting.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # Unknown API paths get the JSON error envelope even in DEBUG (Django's HTML 404 page is for non-API paths).
    re_path(r"^api/.*$", api_not_found),
]
