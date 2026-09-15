"""Company configuration, time zone handling and audit stamping."""

from __future__ import annotations

import datetime as dt
import zoneinfo

import pytest
from django.core.exceptions import ValidationError

from ztech_sales.core.context import request_context
from ztech_sales.core.models import AuditEvent, Company, Currency
from ztech_sales.core.services.audit import build_change_set, record_audit

pytestmark = pytest.mark.django_db


def test_the_company_carries_its_own_time_zone(company):
    assert company.timezone == "Asia/Muscat"
    assert company.tzinfo == zoneinfo.ZoneInfo("Asia/Muscat")


def test_dates_are_evaluated_in_the_company_zone_not_in_utc(company):
    """A date-sensitive rule must not flip a day early or late.

    Muscat is UTC+4, so 21:30 UTC is already the following day locally. A
    quotation that expires "today" has to mean today in Oman.
    """
    late_utc = dt.datetime(2026, 3, 10, 21, 30, tzinfo=dt.UTC)
    assert late_utc.date() == dt.date(2026, 3, 10)
    assert company.localtime(late_utc).date() == dt.date(2026, 3, 11)


def test_an_unknown_time_zone_is_refused(company):
    company.timezone = "Middle_Earth/Shire"
    with pytest.raises(ValidationError):
        company.full_clean(exclude=["currency"])


def test_the_company_currency_drives_monetary_precision(company):
    assert company.currency.code == "OMR"
    assert company.decimal_places == 3
    assert company.rounding_mode == "half_up"


def test_seeded_currency_precision_follows_iso_4217(company):
    precision = dict(Currency.objects.values_list("code", "decimal_places"))
    assert precision["OMR"] == 3
    assert precision["USD"] == 2
    assert precision["AED"] == 2


def test_the_default_company_is_resolved_unambiguously(company):
    assert Company.objects.default() == company


def test_resolving_the_default_refuses_to_guess_between_two_companies(company):
    Company.objects.create(
        code="second",
        legal_name="Second Company LLC",
        currency=Currency.objects.get(code="OMR"),
        timezone="Asia/Muscat",
    )
    # Guessing would mean writing a record against the wrong legal owner.
    with pytest.raises(Company.MultipleObjectsReturned):
        Company.objects.default()


def test_a_change_set_lists_only_what_actually_changed():
    before = {"name": "A", "city": "Muscat", "is_active": True}
    after = {"name": "B", "city": "Muscat", "is_active": True}
    assert build_change_set(before, after) == {"name": {"from": "A", "to": "B"}}


def test_a_change_set_redacts_secrets_even_if_a_caller_passes_them():
    changes = build_change_set({"password": "old"}, {"password": "new"})
    assert changes == {"password": {"from": "[redacted]", "to": "[redacted]"}}


def test_an_audit_entry_keeps_the_actor_name_and_the_request_id(company, rep_user):
    with request_context(user=rep_user, ip_address="203.0.113.9", source="web") as ctx:
        entry = record_audit(
            company=company,
            action="customer.created",
            entity_type="customers.customer",
            entity_id=company.id,
            entity_label="Acme LLC",
            summary="Created customer Acme LLC.",
        )
    assert entry.actor == rep_user
    assert entry.actor_label == f"{rep_user.full_name} <{rep_user.email}>"
    assert entry.request_id == ctx.request_id
    assert entry.ip_address == "203.0.113.9"


def test_an_audit_entry_survives_the_actor_being_removed(company, rep_user):
    with request_context(user=rep_user):
        entry = record_audit(company=company, action="customer.created", entity_type="customers.customer")
    label = entry.actor_label
    rep_user.delete()

    entry = AuditEvent.objects.get(pk=entry.pk)
    assert entry.actor is None
    # The name is copied onto the row, so the trail stays readable.
    assert entry.actor_label == label


def test_background_work_is_audited_as_the_system_not_as_a_user(company):
    with request_context(source="worker"):
        entry = record_audit(company=company, action="email.sent", entity_type="communications.message")
    assert entry.actor is None
    assert entry.actor_label == "system"
    assert entry.source == "worker"
