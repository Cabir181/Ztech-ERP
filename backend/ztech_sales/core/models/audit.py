"""Append-only audit trail."""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models
from django.utils import timezone


class AuditEventQuerySet(models.QuerySet):
    def for_entity(self, entity_type: str, entity_id: Any) -> AuditEventQuerySet:
        return self.filter(entity_type=entity_type, entity_id=entity_id)

    def delete(self):  # pragma: no cover - guarded, never exercised in normal flow
        raise NotImplementedError("Audit events are immutable and cannot be deleted.")


class AuditEvent(models.Model):
    """One recorded action.

    Audit events are immutable: they can be inserted and read, never updated or
    deleted. The actor's name and email are copied onto the row so that the
    trail stays readable even if the user account is later renamed, and actor
    identity is never silently lost.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="audit_events")
    occurred_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    actor = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_label = models.CharField(max_length=200, blank=True)

    action = models.CharField(max_length=64, db_index=True, help_text="For example quotation.issued.")
    entity_type = models.CharField(max_length=64, db_index=True, help_text="For example sales.quotation.")
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)
    entity_label = models.CharField(max_length=200, blank=True)

    summary = models.CharField(max_length=400, blank=True)
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Field-level before/after values: {"field": {"from": ..., "to": ...}}.',
    )

    request_id = models.CharField(max_length=36, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    source = models.CharField(max_length=24, default="web", help_text="web, worker, command or integration.")

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        db_table = "core_audit_event"
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["company", "entity_type", "entity_id"], name="idx_audit_entity"),
            models.Index(fields=["company", "-occurred_at"], name="idx_audit_recent"),
        ]

    def __str__(self) -> str:
        return f"{self.occurred_at:%Y-%m-%d %H:%M:%S} {self.action} {self.entity_label}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValueError("Audit events are immutable and cannot be modified once written.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any):  # pragma: no cover - guarded
        raise NotImplementedError("Audit events are immutable and cannot be deleted.")
