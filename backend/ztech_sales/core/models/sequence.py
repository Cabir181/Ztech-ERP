"""Gap-free document numbering."""

from __future__ import annotations

from django.db import models, transaction

from ztech_sales.core.models.base import CompanyOwnedModel


class ResetPeriod(models.TextChoices):
    NEVER = "never", "Never"
    YEARLY = "yearly", "Every year"
    MONTHLY = "every month", "Every month"


class DocumentSequence(CompanyOwnedModel):
    """Allocates the human-readable reference printed on a customer document.

    Numbers are allocated under a row lock inside the caller's transaction, so
    two users saving at the same moment can never receive the same reference.
    If the surrounding transaction rolls back, the number is released with it.
    """

    key = models.SlugField(max_length=48, help_text="For example quotation or sales_order.")
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=16, blank=True, help_text="For example QT- or SO-.")
    padding = models.PositiveSmallIntegerField(default=5)
    next_value = models.PositiveIntegerField(default=1)
    reset_period = models.CharField(max_length=16, choices=ResetPeriod.choices, default=ResetPeriod.YEARLY)
    current_period = models.CharField(max_length=8, blank=True, editable=False)
    include_period_in_reference = models.BooleanField(default=True)

    class Meta:
        db_table = "core_document_sequence"
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(fields=["company", "key"], name="uniq_sequence_key_per_company"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.key})"

    def _period_token(self) -> str:
        today = self.company.today()
        if self.reset_period == ResetPeriod.YEARLY:
            return f"{today.year}"
        if self.reset_period == ResetPeriod.MONTHLY:
            return f"{today.year}{today.month:02d}"
        return ""

    @classmethod
    def allocate(cls, company, key: str) -> str:
        """Return the next reference for ``key``. Must run inside a transaction."""
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError(
                "DocumentSequence.allocate must be called inside a transaction so that an "
                "allocated number is released if the surrounding work is rolled back."
            )
        sequence = cls.objects.select_for_update().select_related("company").get(company=company, key=key)
        period = sequence._period_token()
        if period != sequence.current_period:
            sequence.current_period = period
            sequence.next_value = 1
        number = sequence.next_value
        sequence.next_value = number + 1
        sequence.save(update_fields=["next_value", "current_period"])

        parts = [sequence.prefix] if sequence.prefix else []
        if period and sequence.include_period_in_reference:
            parts.append(f"{period}-")
        parts.append(str(number).zfill(sequence.padding))
        return "".join(parts)
