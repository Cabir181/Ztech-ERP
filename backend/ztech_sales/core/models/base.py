"""Abstract base models: identifiers, auditing columns and optimistic locking."""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models
from django.utils import timezone

from ztech_sales.core.context import current_user
from ztech_sales.core.exceptions import BusinessRuleError, StaleObjectError


class UUIDModel(models.Model):
    """Primary keys are UUIDs so that identifiers are not guessable or countable.

    Note that unguessable identifiers are a defence in depth measure only. Every
    read and write is still authorised explicitly; nothing in this application
    treats knowledge of an identifier as permission to use it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)
    created_by = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        "core.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    class Meta:
        abstract = True

    def _stamp(self, creating: bool) -> list[str]:
        """Set the audit columns and return the field names that were touched."""
        touched = ["updated_at"]
        self.updated_at = timezone.now()
        actor = current_user()
        if actor is not None:
            self.updated_by = actor
            touched.append("updated_by")
            if creating and self.created_by_id is None:
                self.created_by = actor
        return touched


class VersionedModel(models.Model):
    """Optimistic concurrency control.

    ``version`` starts at 1 and increases by one on every successful update. A
    client that submits a stale version receives HTTP 409 and its write is
    rejected, rather than silently overwriting a change made by someone else.

    The guard is only sound when the row is read inside the same transaction
    that writes it. Services therefore use::

        with transaction.atomic():
            obj = Model.objects.select_for_update().get(pk=pk)
            obj.assert_version(submitted_version)
            ...
            obj.save()
    """

    version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        abstract = True

    def assert_version(self, expected_version: Any) -> None:
        if expected_version is None or expected_version == "":
            raise BusinessRuleError(
                "A version must be supplied when updating an existing record.",
                details={"version": ["This field is required when updating an existing record."]},
            )
        try:
            expected = int(expected_version)
        except (TypeError, ValueError) as exc:
            raise BusinessRuleError(
                "The supplied version is not a number.",
                details={"version": ["Must be an integer."]},
            ) from exc
        if expected != self.version:
            raise StaleObjectError(
                details={"current_version": self.version, "submitted_version": expected},
            )


class BaseModel(UUIDModel, TimeStampedModel, VersionedModel):
    """Identifier, audit columns and optimistic locking for every business record."""

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        creating = self._state.adding
        touched = self._stamp(creating)
        if not creating:
            self.version = (self.version or 1) + 1
            touched.append("version")
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = sorted(set(update_fields) | set(touched))
        super().save(*args, **kwargs)


class CompanyOwnedQuerySet(models.QuerySet):
    def for_company(self, company: Any) -> CompanyOwnedQuerySet:
        """Restrict to a single owning company.

        Applied by every company-owned view before any other filtering, so a
        record can never be reached across a company boundary.
        """
        return self.filter(company=company)


class CompanyOwnedModel(BaseModel):
    """A business record owned by exactly one company.

    Release 1 deploys one legal company per environment, but ownership is
    modelled explicitly from the start so that adding a second company later is
    a configuration change rather than a schema rewrite.
    """

    company = models.ForeignKey("core.Company", on_delete=models.PROTECT, related_name="+")

    objects = CompanyOwnedQuerySet.as_manager()

    class Meta:
        abstract = True
