"""Root URL configuration.

The API lives under ``/api/``. The compiled single-page frontend is served from
the same origin, so session cookies and CSRF protection apply to every request
without any cross-origin configuration.
"""

from __future__ import annotations

from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from ztech_sales.core.views import spa_index

urlpatterns = [
    path("api/", include(("ztech_sales.core.urls", "core"), namespace="core")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="schema-docs",
    ),
    # Client-side routes fall through to the interface. Declared last so it can
    # never shadow an API route, and excluding /api/ and /static/ so a mistyped
    # endpoint still returns a JSON 404 rather than an HTML page.
    re_path(r"^(?!api/|static/).*$", spa_index, name="spa"),
]

# API paths that match nothing, and unhandled server errors, answer with the
# same JSON envelope as every other error rather than with an HTML page a JSON
# client cannot read.
handler404 = "ztech_sales.core.views.not_found"
handler500 = "ztech_sales.core.views.server_error"
