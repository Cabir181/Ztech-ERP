"""Per-request ambient context.

``RequestContextMiddleware`` populates these context variables at the start of
each request and clears them afterwards. Model and service code reads them to
stamp ``created_by``/``updated_by`` and to attach the request id, client address
and user agent to audit events, without every function having to accept a
request object it does not otherwise need.

Background worker code sets the same variables explicitly through
``request_context``.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RequestContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user: Any = None
    ip_address: str | None = None
    user_agent: str = ""
    source: str = "web"


_current: ContextVar[RequestContext | None] = ContextVar("ztech_request_context", default=None)


def get_context() -> RequestContext | None:
    return _current.get()


def current_user() -> Any:
    ctx = _current.get()
    if ctx is None:
        return None
    user = ctx.user
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


def current_request_id() -> str:
    ctx = _current.get()
    return ctx.request_id if ctx else ""


def set_context(ctx: RequestContext):
    return _current.set(ctx)


def reset_context(token) -> None:
    _current.reset(token)


@contextlib.contextmanager
def request_context(**kwargs: Any) -> Iterator[RequestContext]:
    """Install a context for a block of work (used by the worker and by tests)."""
    ctx = RequestContext(**kwargs)
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)
