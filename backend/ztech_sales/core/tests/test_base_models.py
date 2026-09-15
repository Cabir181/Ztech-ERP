"""Behaviour of the abstract base models every business record inherits."""

from __future__ import annotations

import pytest
from django.db import transaction

from ztech_sales.core.context import request_context
from ztech_sales.core.exceptions import BusinessRuleError, StaleObjectError
from ztech_sales.core.models import DocumentSequence, Role, User

pytestmark = pytest.mark.django_db


def test_a_new_record_starts_at_version_one(company):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    assert role.version == 1


def test_every_save_advances_the_version(company):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    role.name = "Renamed"
    role.save()
    role.refresh_from_db()
    assert role.version == 2


def test_assert_version_accepts_the_current_value(company):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    role.assert_version(1)
    role.assert_version("1")  # query strings and JSON both arrive as text


def test_assert_version_rejects_a_stale_value(company):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    role.save()
    with pytest.raises(StaleObjectError) as excinfo:
        role.assert_version(1)
    assert excinfo.value.details == {"current_version": 2, "submitted_version": 1}


@pytest.mark.parametrize("bad", [None, "", "not-a-number"])
def test_assert_version_refuses_a_missing_or_unusable_value(company, bad):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    with pytest.raises(BusinessRuleError):
        role.assert_version(bad)


def test_the_acting_user_is_stamped_onto_created_and_updated_by(company, rep_user, manager_user):
    with request_context(user=rep_user):
        role = Role.objects.create(company=company, code="temp", name="Temporary")
    assert role.created_by == rep_user
    assert role.updated_by == rep_user

    with request_context(user=manager_user):
        role.name = "Renamed"
        role.save()
    role.refresh_from_db()
    # The original author is preserved; only the last editor changes.
    assert role.created_by == rep_user
    assert role.updated_by == manager_user


def test_saving_outside_a_request_leaves_the_actor_unset(company):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    assert role.created_by is None


def test_update_fields_still_writes_the_bookkeeping_columns(company):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    before = role.updated_at
    role.name = "Renamed"
    role.save(update_fields=["name"])
    role.refresh_from_db()
    # A partial save must not skip the version counter, or optimistic locking
    # would silently stop working for that code path.
    assert role.name == "Renamed"
    assert role.version == 2
    assert role.updated_at > before


def test_company_scoping_excludes_another_companys_rows(company):
    from ztech_sales.core.models import Company, Currency

    other = Company.objects.create(
        code="other",
        legal_name="Other Company LLC",
        currency=Currency.objects.get(code="OMR"),
        timezone="Asia/Muscat",
    )
    Role.objects.create(company=other, code="foreign", name="Foreign role")

    visible = {role.code for role in Role.objects.for_company(company)}
    assert "foreign" not in visible
    assert Role.objects.for_company(other).count() == 1


def test_identifiers_are_uuids_not_sequential_integers(company):
    import uuid

    role = Role.objects.create(company=company, code="temp", name="Temporary")
    assert isinstance(role.id, uuid.UUID)


def test_a_sequence_resets_when_its_period_rolls_over(company):
    with transaction.atomic():
        first = DocumentSequence.allocate(company, "customer")
    sequence = DocumentSequence.objects.get(company=company, key="customer")
    assert first == f"CUS-{company.today().year}-00001"

    # Simulate the next period arriving.
    sequence.current_period = "1999"
    sequence.next_value = 57
    sequence.save()

    with transaction.atomic():
        second = DocumentSequence.allocate(company, "customer")
    assert second == f"CUS-{company.today().year}-00001"


def test_user_email_addresses_are_normalised_on_save():
    user = User.objects.create_user(email="  Mixed.Case@Example.COM ", full_name="  Spaced Name  ")
    assert user.email == "mixed.case@example.com"
    assert user.full_name == "Spaced Name"


def test_a_user_created_without_a_password_cannot_sign_in():
    user = User.objects.create_user(email="nopassword@example.com", full_name="No Password")
    assert user.has_usable_password() is False
    assert user.check_password("") is False
