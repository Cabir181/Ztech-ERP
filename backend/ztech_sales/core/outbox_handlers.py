"""Registry of outbox topic handlers.

Increment A ships the registry and the worker loop. Handlers for document
rendering, email delivery and integration events are registered by their own
modules in later increments; nothing here assumes which topics exist.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Handler = Callable[[Any], dict[str, Any] | None]

_HANDLERS: dict[str, Handler] = {}


class HandlerNotRegistered(Exception):
    """Raised when a message names a topic no handler is registered for."""


def register(topic: str) -> Callable[[Handler], Handler]:
    def decorator(func: Handler) -> Handler:
        if topic in _HANDLERS:
            raise RuntimeError(f"A handler for topic {topic!r} is already registered.")
        _HANDLERS[topic] = func
        return func

    return decorator


def registered_topics() -> list[str]:
    return sorted(_HANDLERS)


def dispatch(message: Any) -> dict[str, Any]:
    handler = _HANDLERS.get(message.topic)
    if handler is None:
        raise HandlerNotRegistered(
            f"No handler is registered for outbox topic {message.topic!r}. "
            f"Registered topics: {', '.join(registered_topics()) or 'none'}."
        )
    return handler(message) or {}


@register("core.noop")
def _noop(message: Any) -> dict[str, Any]:
    """Health-check topic used to prove the worker is running end to end."""
    return {"echo": message.payload}
