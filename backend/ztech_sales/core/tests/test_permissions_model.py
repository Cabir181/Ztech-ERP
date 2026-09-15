"""Role resolution and the segregation of duties it enforces."""

from __future__ import annotations

import pytest

from ztech_sales.core.models import Role, User, UserRole
from ztech_sales.core.permissions import (
    ALL_PERMISSION_CODES,
    APPROVER,
    BUILTIN_ROLES,
    PERMISSIONS,
    validate_permission_codes,
)

pytestmark = pytest.mark.django_db


def test_permission_codes_are_unique():
    codes = [p.code for p in PERMISSIONS]
    assert len(codes) == len(set(codes))


def test_builtin_roles_only_reference_known_permissions():
    for code, spec in BUILTIN_ROLES.items():
        unknown = validate_permission_codes(list(spec["permissions"]))
        assert unknown == [], f"role {code} references unknown permission(s) {unknown}"


def test_representative_cannot_see_other_users_quotations(rep_user, company):
    held = rep_user.get_permission_codes(company)
    assert "quotation.view.own" in held
    assert "quotation.view.all" not in held


def test_manager_sees_every_quotation(manager_user, company):
    held = manager_user.get_permission_codes(company)
    assert "quotation.view.all" in held


def test_administrator_flag_does_not_confer_approval_authority(admin_user, company):
    # Approval authority is a segregation-of-duties control: it is granted by a
    # role, never by an account flag, so "who may approve" is always answerable
    # from the role assignments.
    held = admin_user.get_permission_codes(company)
    assert held == ALL_PERMISSION_CODES - {"approval.decide"}
    assert not admin_user.has_permission("approval.decide", company)


def test_approver_role_grants_approval_authority(approver_user, company):
    assert approver_user.has_permission("approval.decide", company)


def test_deactivating_a_user_removes_every_permission(rep_user, company):
    assert rep_user.get_permission_codes(company)
    rep_user.is_active = False
    rep_user.save()
    rep_user.clear_permission_cache()
    assert rep_user.get_permission_codes(company) == frozenset()


def test_retired_permission_codes_are_ignored_not_granted(company, roles, rep_user):
    # An upgrade that retires a code must not leave a role granting something the
    # application no longer understands.
    role = roles["sales_representative"]
    role.role_permissions.create(code="quotation.time_travel")
    rep_user.clear_permission_cache()
    held = rep_user.get_permission_codes(company)
    assert "quotation.time_travel" not in held
    assert held <= ALL_PERMISSION_CODES


def test_permissions_are_scoped_to_the_owning_company(company, rep_user):
    from ztech_sales.core.models import Company, Currency

    other = Company.objects.create(
        code="other",
        legal_name="Other Company LLC",
        currency=Currency.objects.get(code="OMR"),
        timezone="Asia/Muscat",
    )
    # The same person holds nothing at all in a company they have no role in.
    assert rep_user.get_permission_codes(other) == frozenset()


def test_role_set_permissions_replaces_rather_than_appends(company, roles):
    role = Role.objects.create(company=company, code="temp", name="Temporary")
    role.set_permissions(["customer.view", "catalog.view"])
    assert role.permission_codes == ["catalog.view", "customer.view"]
    role.set_permissions(["customer.view"])
    assert role.permission_codes == ["customer.view"]


def test_approver_role_is_additive_to_a_sales_role(company, roles):
    user = User.objects.create_user(email="dual@testco.example", full_name="Dual Hat", password=None)
    UserRole.objects.create(user=user, role=roles["sales_representative"])
    UserRole.objects.create(user=user, role=roles[APPROVER])
    held = user.get_permission_codes(company)
    assert {"quotation.create", "approval.decide"} <= held
