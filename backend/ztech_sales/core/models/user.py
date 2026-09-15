"""User accounts, roles and role assignment."""

from __future__ import annotations

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from ztech_sales.core.models.base import BaseModel, CompanyOwnedModel, UUIDModel, VersionedModel
from ztech_sales.core.models.company import CODE_VALIDATOR
from ztech_sales.core.permissions import ALL_PERMISSION_CODES

# Duties that a break-glass administrator flag deliberately does NOT confer.
# Approval authority is a segregation-of-duties control and must be granted
# explicitly through a role, so that "who may approve" is always answerable from
# the role assignments rather than from an account flag.
ADMINISTRATOR_EXCLUDED_PERMISSIONS = frozenset({"approval.decide"})


class UserManager(BaseUserManager):
    use_in_migrations = False

    def normalize_email(self, email: str | None) -> str:
        return (email or "").strip().lower()

    def create_user(self, email: str, full_name: str, password: str | None = None, **extra) -> User:
        email = self.normalize_email(email)
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email, full_name=full_name.strip(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password", "last_login"])
        user.save()
        return user

    def create_administrator(self, email: str, full_name: str, password: str, **extra) -> User:
        extra.setdefault("is_system_administrator", True)
        extra.setdefault("is_active", True)
        return self.create_user(email=email, full_name=full_name, password=password, **extra)

    def active(self):
        return self.get_queryset().filter(is_active=True)


class User(UUIDModel, VersionedModel, AbstractBaseUser):
    """A named person who signs in to this deployment.

    Sign-in is by email address. There is no shared or generic account: every
    audit entry, approval decision and acceptance record names a real user, so
    accounts are never reused between people.
    """

    email = models.EmailField(unique=True, max_length=254)
    full_name = models.CharField(max_length=150)
    job_title = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)

    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Inactive users cannot sign in and lose access immediately, including on a session "
            "that is already open."
        ),
    )
    is_system_administrator = models.BooleanField(
        default=False,
        help_text=(
            "Break-glass flag granting every permission except approval authority, which must be "
            "granted through a role."
        ),
    )
    must_change_password = models.BooleanField(default=False)

    failed_login_count = models.PositiveIntegerField(default=0, editable=False)
    locked_until = models.DateTimeField(null=True, blank=True, editable=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, editable=False)

    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "core_user"
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.full_name = (self.full_name or "").strip()
        creating = self._state.adding
        self.updated_at = timezone.now()
        if not creating:
            self.version = (self.version or 1) + 1
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = sorted(set(kwargs["update_fields"]) | {"version", "updated_at"})
        super().save(*args, **kwargs)

    # -- authentication state ------------------------------------------------

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > timezone.now()

    def register_failed_login(self, max_attempts: int, lockout_seconds: int) -> None:
        self.failed_login_count += 1
        fields = ["failed_login_count"]
        if self.failed_login_count >= max_attempts:
            self.locked_until = timezone.now() + timezone.timedelta(seconds=lockout_seconds)
            fields.append("locked_until")
        self.save(update_fields=fields)

    def register_successful_login(self, ip_address: str | None) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login = timezone.now()
        self.last_login_ip = ip_address
        self.save(update_fields=["failed_login_count", "locked_until", "last_login", "last_login_ip"])

    # -- authorisation -------------------------------------------------------

    def role_assignments(self, company):
        return (
            UserRole.objects.filter(user=self, role__company=company, role__is_active=True)
            .select_related("role")
            .prefetch_related("role__role_permissions")
        )

    def get_roles(self, company) -> list[Role]:
        return [assignment.role for assignment in self.role_assignments(company)]

    @property
    def roles(self) -> list[Role]:
        """Every role this user holds, across companies.

        Reads the ``role_assignments_set__role`` prefetch when the caller set
        one up, so serialising a page of users stays at a fixed query count.
        """
        return [assignment.role for assignment in self.role_assignments_set.all()]

    def get_permission_codes(self, company) -> frozenset[str]:
        """Resolve the permission codes this user holds within ``company``.

        The result is cached on the instance for the lifetime of the request, so
        a view that checks several permissions issues a single query.
        """
        cache_key = f"_permission_cache_{company.pk}"
        cached = getattr(self, cache_key, None)
        if cached is not None:
            return cached

        if not self.is_active:
            codes: frozenset[str] = frozenset()
        else:
            granted = {
                permission.code
                for assignment in self.role_assignments(company)
                for permission in assignment.role.role_permissions.all()
            }
            if self.is_system_administrator:
                granted |= set(ALL_PERMISSION_CODES - ADMINISTRATOR_EXCLUDED_PERMISSIONS)
            # Codes retired by an upgrade are ignored rather than trusted.
            codes = frozenset(granted & ALL_PERMISSION_CODES)

        setattr(self, cache_key, codes)
        return codes

    def has_permission(self, code: str, company) -> bool:
        return code in self.get_permission_codes(company)

    def has_any_permission(self, codes: list[str], company) -> bool:
        held = self.get_permission_codes(company)
        return any(code in held for code in codes)

    def clear_permission_cache(self) -> None:
        for attribute in [name for name in vars(self) if name.startswith("_permission_cache_")]:
            delattr(self, attribute)


class Role(CompanyOwnedModel):
    """A named bundle of permissions that can be assigned to users."""

    code = models.SlugField(max_length=48, validators=[CODE_VALIDATOR])
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(
        default=False,
        help_text="Seeded with the client environment. Its code cannot be changed or deleted.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "core_role"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_role_code_per_company"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def permission_codes(self) -> list[str]:
        return sorted(permission.code for permission in self.role_permissions.all())

    def set_permissions(self, codes: list[str]) -> None:
        """Replace this role's permissions with ``codes``.

        Unknown codes are rejected by :func:`validate_permission_codes` in the
        service layer before this is called.
        """
        wanted = set(codes)
        existing = {permission.code for permission in self.role_permissions.all()}
        RolePermission.objects.filter(role=self, code__in=sorted(existing - wanted)).delete()
        RolePermission.objects.bulk_create(
            [RolePermission(role=self, code=code) for code in sorted(wanted - existing)]
        )


class RolePermission(models.Model):
    """One permission code granted by one role."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    code = models.CharField(max_length=64)

    class Meta:
        db_table = "core_role_permission"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["role", "code"], name="uniq_permission_per_role"),
        ]

    def __str__(self) -> str:
        return self.code


class UserRole(BaseModel):
    """Assignment of a role to a user, retained as evidence of who granted it."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments_set")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    granted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    granted_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "core_user_role"
        ordering = ["-granted_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_role_per_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user.full_name} -> {self.role.name}"
