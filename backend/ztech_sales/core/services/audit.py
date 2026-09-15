"""Writing audit entries."""

from __future__ import annotations

from typing import Any

from ztech_sales.core.context import get_context
from ztech_sales.core.models import AuditEvent

# Values that must never be copied into the audit trail, even if a caller passes
# them in a change set by mistake.
REDACTED_FIELDS = frozenset({"password", "new_password", "current_password", "token", "secret"})
REDACTED_PLACEHOLDER = "[redacted]"


def _serialisable(value: Any) -> Any:
    """Render a field value as something JSON can hold."""
    from decimal import Decimal
    from uuid import UUID

    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list | tuple):
        return [_serialisable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialisable(item) for key, item in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def build_change_set(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return only the fields whose value actually changed."""
    changes: dict[str, dict[str, Any]] = {}
    for field in sorted(set(before) | set(after)):
        old = before.get(field)
        new = after.get(field)
        if old == new:
            continue
        if field in REDACTED_FIELDS:
            changes[field] = {"from": REDACTED_PLACEHOLDER, "to": REDACTED_PLACEHOLDER}
            continue
        changes[field] = {"from": _serialisable(old), "to": _serialisable(new)}
    return changes


def record_audit(
    *,
    company,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    entity_label: str = "",
    summary: str = "",
    changes: dict[str, Any] | None = None,
    actor: Any = None,
    source: str | None = None,
) -> AuditEvent:
    """Write one immutable audit entry.

    Called inside the same transaction as the change it describes, so the trail
    and the data can never disagree about whether something happened.
    """
    context = get_context()
    if actor is None and context is not None:
        candidate = context.user
        if candidate is not None and getattr(candidate, "is_authenticated", False):
            actor = candidate

    safe_changes = {key: value for key, value in (changes or {}).items() if key not in REDACTED_FIELDS}

    return AuditEvent.objects.create(
        company=company,
        actor=actor,
        actor_label=(f"{actor.full_name} <{actor.email}>" if actor is not None else "system"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label[:200],
        summary=summary[:400],
        changes=_serialisable(safe_changes),
        request_id=context.request_id if context else "",
        ip_address=context.ip_address if context else None,
        user_agent=context.user_agent if context else "",
        source=source or (context.source if context else "system"),
    )
