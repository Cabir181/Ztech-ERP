"""Application exceptions and the uniform API error envelope.

Every error the API returns has the same shape::

    {"error": {"code": "...", "message": "...", "details": {...}}}

``code`` is a stable machine-readable string that the frontend switches on;
``message`` is safe to show to an internal user; ``details`` carries per-field
validation errors when there are any.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class ApplicationError(APIException):
    """Base class for errors this application raises deliberately."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "application_error"
    default_detail = "The request could not be completed."

    def __init__(self, detail: str | None = None, *, details: dict[str, Any] | None = None):
        super().__init__(detail or self.default_detail)
        self.details = details or {}


class BusinessRuleError(ApplicationError):
    """A request was well formed but violates a documented business rule."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "business_rule_violated"
    default_detail = "This action is not allowed in the record's current state."


class InvalidTransitionError(BusinessRuleError):
    error_code = "invalid_transition"
    default_detail = "This state transition is not allowed."


class StaleObjectError(ApplicationError):
    """The caller's copy of the record is out of date.

    Returned as HTTP 409 so the frontend can reload and show the user what
    changed instead of silently overwriting another user's work.
    """

    status_code = status.HTTP_409_CONFLICT
    error_code = "stale_object"
    default_detail = (
        "This record was changed by someone else since you opened it. "
        "Reload the record and reapply your changes."
    )


class PermissionDeniedError(ApplicationError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "permission_denied"
    default_detail = "You do not have permission to perform this action."


class ConfigurationError(ApplicationError):
    """A required piece of deployment configuration is missing.

    Used, for example, when email delivery is requested but no SMTP host is
    configured. The application reports this honestly rather than reporting a
    message as sent.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "not_configured"
    default_detail = "This feature is not configured on this deployment."


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return payload


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF exception handler producing the uniform error envelope."""
    if isinstance(exc, DjangoValidationError):
        details = exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
        return Response(
            _envelope("validation_failed", "The submitted data is not valid.", details),
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, DjangoPermissionDenied):
        return Response(
            _envelope("permission_denied", PermissionDeniedError.default_detail),
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, Http404):
        # Records the caller may not see are reported as missing rather than
        # forbidden, so the API never confirms that an identifier exists.
        return Response(
            _envelope("not_found", "The requested record does not exist."),
            status=status.HTTP_404_NOT_FOUND,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled exception while serving %s", context.get("request"))
        return Response(
            _envelope("internal_error", "An unexpected error occurred. The incident has been logged."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, ApplicationError):
        return Response(
            _envelope(exc.error_code, str(exc.detail), exc.details),
            status=exc.status_code,
        )

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        code = getattr(exc, "default_code", "error")
        return Response(_envelope(str(code), str(detail["detail"])), status=response.status_code)

    return Response(
        _envelope("validation_failed", "The submitted data is not valid.", detail),
        status=response.status_code,
    )
