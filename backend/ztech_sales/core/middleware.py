"""Request-scoped context middleware."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from ztech_sales.core.context import RequestContext, reset_context, set_context

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"


def client_ip(request: HttpRequest) -> str | None:
    """Best-effort client address.

    ``X-Forwarded-For`` is only consulted for its left-most entry and is used
    for logging and the audit trail, never for an authorisation decision.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    return request.META.get("REMOTE_ADDR") or None


class RequestContextMiddleware:
    """Attach a request id, the acting user and client details to the request.

    The same values are exposed through :mod:`ztech_sales.core.context` so that
    model and service code can stamp audit columns without being handed a
    request object.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.META.get(REQUEST_ID_HEADER, "").strip()
        # An inbound id is echoed for traceability but never trusted verbatim.
        try:
            request_id = str(uuid.UUID(incoming))
        except (ValueError, AttributeError):
            request_id = str(uuid.uuid4())

        context = RequestContext(
            request_id=request_id,
            user=getattr(request, "user", None),
            ip_address=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            source="web",
        )
        request.request_id = request_id
        token = set_context(context)
        try:
            # request.user is lazy: refresh the context once the view has
            # resolved it, so audit entries name the real actor.
            context.user = getattr(request, "user", None)
            response = self.get_response(request)
        finally:
            reset_context(token)
        response[RESPONSE_HEADER] = request_id
        return response
