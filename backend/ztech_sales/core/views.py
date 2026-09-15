"""Non-API views."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """Return the uniform error envelope when CSRF validation fails.

    Without this, Django renders an HTML page that a JSON client cannot read.
    The reason string is deliberately not echoed back to the caller.
    """
    return JsonResponse(
        {
            "error": {
                "code": "csrf_failed",
                "message": (
                    "The request could not be verified. Reload the page and try again; "
                    "if this keeps happening, sign in again."
                ),
            }
        },
        status=403,
    )


def spa_index(request: HttpRequest) -> HttpResponse:
    """Serve the single-page interface for any non-API path.

    The interface routes on the client, so a deep link such as ``/users`` has to
    return ``index.html`` rather than 404. Only paths that are not under
    ``/api/`` or ``/static/`` reach this view.

    The document itself is never cached: it names the hashed asset bundles, so a
    cached copy would keep pinning an old release after a deployment.
    """
    index = Path(settings.FRONTEND_INDEX)
    if not index.is_file():
        return HttpResponse(
            "The interface has not been built for this deployment. "
            "Run `npm run build` in the frontend directory, or use the Vite dev server.",
            status=501,
            content_type="text/plain; charset=utf-8",
        )
    response = HttpResponse(index.read_bytes(), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store, must-revalidate"
    return response


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    """JSON 404 for API paths.

    Non-API paths never reach here: the catch-all route hands them to the
    interface so a client-side deep link still works.
    """
    return JsonResponse(
        {"error": {"code": "not_found", "message": "The requested endpoint does not exist."}},
        status=404,
    )


def server_error(request: HttpRequest) -> JsonResponse:
    """JSON 500 that reveals nothing about what went wrong internally."""
    return JsonResponse(
        {
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. The incident has been logged.",
            }
        },
        status=500,
    )
