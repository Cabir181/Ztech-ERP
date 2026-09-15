"""Durable database outbox for asynchronous work and outbound integration events.

Everything that must happen after a transaction commits - rendering a document,
sending an email, publishing an integration event - is written to this table
inside the same transaction as the business change. A separate worker process
claims rows and executes them.

This gives at-least-once delivery with no additional infrastructure: no broker,
no Redis and no second datastore that can disagree with the database about
whether the business change actually happened.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models, transaction
from django.utils import timezone


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed - will retry"
    DEAD = "dead", "Failed - retries exhausted"


class OutboxQuerySet(models.QuerySet):
    def due(self) -> OutboxQuerySet:
        return self.filter(
            status__in=[OutboxStatus.PENDING, OutboxStatus.FAILED],
            available_at__lte=timezone.now(),
        )


class OutboxManager(models.Manager.from_queryset(OutboxQuerySet)):
    def enqueue(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        company=None,
        idempotency_key: str | None = None,
        available_at=None,
        max_attempts: int = 8,
    ) -> OutboxMessage | None:
        """Queue a message.

        When ``idempotency_key`` is supplied and a message with that key already
        exists, nothing is queued and ``None`` is returned. That is what makes a
        retried request produce one email and one integration event rather than
        two.
        """
        if idempotency_key and self.filter(idempotency_key=idempotency_key).exists():
            return None
        return self.create(
            topic=topic,
            payload=payload,
            company=company,
            idempotency_key=idempotency_key or None,
            available_at=available_at or timezone.now(),
            max_attempts=max_attempts,
        )

    def claim_batch(self, *, worker_id: str, limit: int = 10) -> list[OutboxMessage]:
        """Atomically claim up to ``limit`` due messages for this worker.

        ``SELECT ... FOR UPDATE SKIP LOCKED`` lets several workers run against
        the same table without any of them blocking or double-claiming a row.
        """
        with transaction.atomic():
            ids = list(
                self.due()
                .select_for_update(skip_locked=True)
                .order_by("available_at", "created_at")
                .values_list("id", flat=True)[:limit]
            )
            if not ids:
                return []
            now = timezone.now()
            self.filter(id__in=ids).update(
                status=OutboxStatus.IN_PROGRESS,
                locked_at=now,
                locked_by=worker_id,
                attempts=models.F("attempts") + 1,
            )
            return list(self.filter(id__in=ids).order_by("available_at", "created_at"))


class OutboxMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "core.Company", null=True, blank=True, on_delete=models.PROTECT, related_name="outbox_messages"
    )

    topic = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=160, unique=True, null=True, blank=True)

    status = models.CharField(max_length=16, choices=OutboxStatus.choices, default=OutboxStatus.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=8)

    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=64, blank=True)

    last_error = models.TextField(blank=True)
    result = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = OutboxManager()

    class Meta:
        db_table = "core_outbox_message"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "available_at"], name="idx_outbox_due"),
            models.Index(fields=["topic", "status"], name="idx_outbox_topic_status"),
        ]

    def __str__(self) -> str:
        return f"{self.topic} [{self.status}]"

    def mark_succeeded(self, result: dict[str, Any] | None = None) -> None:
        self.status = OutboxStatus.SUCCEEDED
        self.completed_at = timezone.now()
        self.result = result or {}
        self.last_error = ""
        self.save(update_fields=["status", "completed_at", "result", "last_error"])

    def mark_failed(self, error: str, *, retry_base_seconds: int = 30) -> None:
        """Record a failure and schedule a retry with exponential backoff."""
        self.last_error = error[:8000]
        if self.attempts >= self.max_attempts:
            self.status = OutboxStatus.DEAD
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "last_error", "completed_at"])
            return
        self.status = OutboxStatus.FAILED
        delay = retry_base_seconds * (2 ** min(self.attempts - 1, 8))
        self.available_at = timezone.now() + timezone.timedelta(seconds=delay)
        self.save(update_fields=["status", "last_error", "available_at"])
