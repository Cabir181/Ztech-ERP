"""User and role administration.

Each function owns one transaction, writes its own audit entry inside it, and
enforces the rules that must not depend on the interface: an administrator
cannot lock themselves out, a built-in role cannot be dismantled, and every
change to who-can-do-what is recorded with the acting user's name.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from ztech_sales.core.exceptions import BusinessRuleError
from ztech_sales.core.models import Role, User, UserRole
from ztech_sales.core.services.audit import build_change_set, record_audit

USER_AUDIT_FIELDS = (
    "email",
    "full_name",
    "job_title",
    "phone",
    "is_active",
    "is_system_administrator",
)

ROLE_AUDIT_FIELDS = ("code", "name", "description", "is_active")


def _user_snapshot(user: User) -> dict[str, Any]:
    snapshot = {field: getattr(user, field) for field in USER_AUDIT_FIELDS}
    snapshot["roles"] = sorted(assignment.role.code for assignment in user.role_assignments_set.all())
    return snapshot


def _role_snapshot(role: Role) -> dict[str, Any]:
    snapshot = {field: getattr(role, field) for field in ROLE_AUDIT_FIELDS}
    snapshot["permissions"] = role.permission_codes
    return snapshot


@transaction.atomic
def create_user(*, company, data: dict[str, Any], actor: User) -> User:
    role_ids = data.pop("role_ids", [])
    password = data.pop("initial_password", None)
    data.pop("version", None)

    user = User.objects.create_user(
        email=data["email"],
        full_name=data["full_name"],
        password=password,
        job_title=data.get("job_title", ""),
        phone=data.get("phone", ""),
        is_active=data.get("is_active", True),
        is_system_administrator=data.get("is_system_administrator", False),
        must_change_password=bool(password),
    )
    _replace_roles(user=user, company=company, role_ids=role_ids, actor=actor)

    record_audit(
        company=company,
        action="user.created",
        entity_type="core.user",
        entity_id=user.id,
        entity_label=user.full_name,
        summary=f"Created user {user.email}.",
        changes=build_change_set({}, _user_snapshot(user)),
        actor=actor,
    )
    return user


@transaction.atomic
def update_user(*, company, user_id: Any, data: dict[str, Any], actor: User) -> User:
    expected_version = data.pop("version", None)
    role_ids = data.pop("role_ids", None)
    data.pop("initial_password", None)

    user = User.objects.select_for_update().get(pk=user_id)
    user.assert_version(expected_version)
    before = _user_snapshot(user)

    # An administrator must not be able to remove their own access and leave the
    # environment without anyone who can restore it.
    if user.pk == actor.pk:
        if data.get("is_active") is False:
            raise BusinessRuleError("You cannot deactivate your own account.")
        if actor.is_system_administrator and data.get("is_system_administrator") is False:
            raise BusinessRuleError("You cannot remove your own administrator access.")

    for field in USER_AUDIT_FIELDS:
        if field in data:
            setattr(user, field, data[field])
    user.full_clean(exclude=["password", "last_login"])
    user.save()

    if role_ids is not None:
        _replace_roles(user=user, company=company, role_ids=role_ids, actor=actor)

    _assert_administrator_remains(company)

    user.clear_permission_cache()
    after = _user_snapshot(user)
    changes = build_change_set(before, after)
    if changes:
        record_audit(
            company=company,
            action="user.updated",
            entity_type="core.user",
            entity_id=user.id,
            entity_label=user.full_name,
            summary=f"Updated user {user.email}.",
            changes=changes,
            actor=actor,
        )
    return user


def _replace_roles(*, user: User, company, role_ids: list[Any], actor: User) -> None:
    wanted = set(Role.objects.filter(id__in=role_ids, company=company).values_list("id", flat=True))
    current = set(UserRole.objects.filter(user=user, role__company=company).values_list("role_id", flat=True))

    UserRole.objects.filter(user=user, role_id__in=sorted(current - wanted)).delete()
    for role_id in sorted(wanted - current):
        UserRole.objects.create(user=user, role_id=role_id, granted_by=actor)
    user.clear_permission_cache()


def _assert_administrator_remains(company) -> None:
    """Refuse a change that would leave nobody able to administer the environment."""
    has_flagged_admin = User.objects.filter(is_active=True, is_system_administrator=True).exists()
    if has_flagged_admin:
        return
    has_role_admin = UserRole.objects.filter(
        user__is_active=True,
        role__company=company,
        role__is_active=True,
        role__role_permissions__code="user.manage",
    ).exists()
    if not has_role_admin:
        raise BusinessRuleError(
            "This change would leave the environment with no active user who can manage users. "
            "Grant administrator access to another account first."
        )


@transaction.atomic
def create_role(*, company, data: dict[str, Any], actor: User) -> Role:
    permissions = data.pop("permission_codes", [])
    data.pop("version", None)
    role = Role(company=company, **data)
    role.full_clean(exclude=["company"])
    role.save()
    role.set_permissions(permissions)

    record_audit(
        company=company,
        action="role.created",
        entity_type="core.role",
        entity_id=role.id,
        entity_label=role.name,
        summary=f"Created role {role.name}.",
        changes=build_change_set({}, _role_snapshot(role)),
        actor=actor,
    )
    return role


@transaction.atomic
def update_role(*, company, role_id: Any, data: dict[str, Any], actor: User) -> Role:
    expected_version = data.pop("version", None)
    permissions = data.pop("permission_codes", None)

    role = Role.objects.select_for_update().get(pk=role_id, company=company)
    role.assert_version(expected_version)
    before = _role_snapshot(role)

    if role.is_system and data.get("is_active") is False:
        raise BusinessRuleError(
            "A built-in role cannot be deactivated. Remove it from the users who hold it instead."
        )

    for field in ROLE_AUDIT_FIELDS:
        if field in data:
            setattr(role, field, data[field])
    role.full_clean(exclude=["company"])
    role.save()

    if permissions is not None:
        role.set_permissions(permissions)

    _assert_administrator_remains(company)

    after = _role_snapshot(role)
    changes = build_change_set(before, after)
    if changes:
        record_audit(
            company=company,
            action="role.updated",
            entity_type="core.role",
            entity_id=role.id,
            entity_label=role.name,
            summary=f"Updated role {role.name}.",
            changes=changes,
            actor=actor,
        )
    return role


@transaction.atomic
def change_own_password(*, company, user: User, new_password: str) -> None:
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    record_audit(
        company=company,
        action="user.password_changed",
        entity_type="core.user",
        entity_id=user.id,
        entity_label=user.full_name,
        summary="Changed their own password.",
        actor=user,
    )
