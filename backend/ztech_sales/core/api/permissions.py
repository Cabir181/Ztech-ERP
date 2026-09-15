"""Permission enforcement for API views.

Authorisation is checked on the server for every request: list, detail, report,
export, file download and state transition alike. Hiding a control in the
interface is a usability measure, never a security measure - a direct API call
without the required permission is refused with the same 403 as a click would
have been.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from ztech_sales.core.exceptions import PermissionDeniedError
from ztech_sales.core.tenancy import get_active_company

SAFE_METHOD_ACTIONS = {"list", "retrieve", "metadata"}


def require_permission(user: Any, company: Any, *codes: str) -> None:
    """Raise :class:`PermissionDeniedError` unless the user holds one of ``codes``."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDeniedError("Authentication is required.")
    if not user.has_any_permission(list(codes), company):
        raise PermissionDeniedError(
            "You do not have permission to perform this action.",
            details={"required_any_of": sorted(codes)},
        )


def has_permission(user: Any, company: Any, *codes: str) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.has_any_permission(list(codes), company)


class HasCompanyPermission(BasePermission):
    """Check ``view.required_permissions`` against the caller's effective roles.

    ``required_permissions`` is either a sequence of codes applying to every
    action, or a mapping keyed by viewset action (``"list"``, ``"create"``, ...)
    or by lower-case HTTP method, with a ``"default"`` fallback. Holding **any**
    of the listed codes is sufficient, which is how a role that may only see its
    own records (``quotation.view.own``) and a role that may see everything
    (``quotation.view.all``) both reach the same endpoint while the queryset
    narrows the rows each of them actually receives.

    A view that declares no ``required_permissions`` is authenticated-only by
    design; that is spelled out per view rather than assumed.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        if user is None or not user.is_authenticated:
            return False

        required = self._required_codes(request, view)
        if not required:
            return True

        company = get_active_company(request)
        # Raising rather than returning False gives the caller the uniform error
        # envelope, including which permission would have been sufficient.
        require_permission(user, company, *required)
        return True

    @staticmethod
    def _required_codes(request: Any, view: Any) -> tuple[str, ...]:
        declared = getattr(view, "required_permissions", None)
        if not declared:
            return ()
        if isinstance(declared, str):
            return (declared,)
        if isinstance(declared, dict):
            action = getattr(view, "action", None) or request.method.lower()
            codes = declared.get(action, declared.get("default", ()))
            return (codes,) if isinstance(codes, str) else tuple(codes)
        return tuple(declared)
