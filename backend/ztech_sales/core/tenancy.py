"""Resolving the company that owns the data in this deployment.

Release 1 serves one legal company per environment, with its own database and
its own private attachment directory. Every query is still scoped by company
explicitly rather than relying on the deployment shape, so that introducing a
second company later does not require revisiting each query.
"""

from __future__ import annotations

from typing import Any

from ztech_sales.core.models import Company

_ATTRIBUTE = "_ztech_active_company"


def get_active_company(request: Any) -> Company:
    """Return the company that owns the data this request may touch.

    Cached per request so that a view checking several permissions and filtering
    several querysets issues one query, not several.
    """
    cached = getattr(request, _ATTRIBUTE, None)
    if cached is not None:
        return cached
    company = Company.objects.select_related("currency").default()
    setattr(request, _ATTRIBUTE, company)
    return company
