"""Serializers for the core (identity and configuration) API."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from ztech_sales.core.models import AuditEvent, Company, Currency, Role, User, UserRole
from ztech_sales.core.permissions import PERMISSIONS, validate_permission_codes


class VersionedSerializer(serializers.ModelSerializer):
    """Adds the optimistic-locking ``version`` field.

    ``version`` is read-only in the serializer and echoed back to the client on
    every read. On update the client sends the version it last read in the
    request body; the view compares it under a row lock and rejects a stale
    write with HTTP 409 rather than overwriting someone else's change.
    """

    version = serializers.IntegerField(read_only=True)


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "code", "name", "symbol", "decimal_places", "rounding_mode", "is_active"]
        read_only_fields = fields


class CompanySerializer(VersionedSerializer):
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.filter(is_active=True), source="currency", write_only=True
    )
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "code",
            "legal_name",
            "trade_name",
            "display_name",
            "currency",
            "currency_id",
            "timezone",
            "tax_registration_number",
            "commercial_registration_number",
            "address_line1",
            "address_line2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "phone",
            "email",
            "website",
            "brand_primary_color",
            "brand_accent_color",
            "logo_path",
            "document_footer",
            "is_active",
            "version",
        ]
        read_only_fields = ["id", "code", "logo_path", "is_active", "version"]


class CompanyBrandingSerializer(serializers.ModelSerializer):
    """The subset of company data the signed-in interface needs to render itself."""

    currency_code = serializers.CharField(source="currency.code", read_only=True)
    currency_symbol = serializers.CharField(source="currency.symbol", read_only=True)
    decimal_places = serializers.IntegerField(source="currency.decimal_places", read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "code",
            "display_name",
            "legal_name",
            "timezone",
            "currency_code",
            "currency_symbol",
            "decimal_places",
            "brand_primary_color",
            "brand_accent_color",
        ]
        read_only_fields = fields


class RoleSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name"]
        read_only_fields = fields


class RoleSerializer(VersionedSerializer):
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=64),
        source="permission_codes",
        required=False,
        allow_empty=True,
    )
    assigned_user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_system",
            "is_active",
            "permissions",
            "assigned_user_count",
            "version",
        ]
        read_only_fields = ["id", "is_system", "assigned_user_count", "version"]

    def validate_permissions(self, value: list[str]) -> list[str]:
        unknown = validate_permission_codes(value)
        if unknown:
            raise serializers.ValidationError(
                f"Unknown permission code(s): {', '.join(unknown)}. "
                "See /api/system/permissions/ for the catalogue."
            )
        return sorted(set(value))

    def validate_code(self, value: str) -> str:
        if self.instance is not None and self.instance.is_system and value != self.instance.code:
            raise serializers.ValidationError("The code of a built-in role cannot be changed.")
        return value


class UserSerializer(VersionedSerializer):
    roles = RoleSummarySerializer(many=True, read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "job_title",
            "phone",
            "is_active",
            "is_system_administrator",
            "must_change_password",
            "is_locked",
            "last_login",
            "date_joined",
            "roles",
            "version",
        ]
        read_only_fields = ["id", "is_locked", "last_login", "date_joined", "roles", "version"]


class UserWriteSerializer(serializers.ModelSerializer):
    """Create and update payload for a user account.

    ``role_ids`` replaces the user's role assignments wholesale, which makes the
    resulting audit entry a complete statement of what the user may now do.
    """

    role_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    initial_password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    version = serializers.IntegerField(required=False)

    class Meta:
        model = User
        fields = [
            "email",
            "full_name",
            "job_title",
            "phone",
            "is_active",
            "is_system_administrator",
            "role_ids",
            "initial_password",
            "version",
        ]

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        queryset = User.objects.filter(email=email)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return email

    def validate_initial_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate_role_ids(self, value: list[Any]) -> list[Any]:
        company = self.context["company"]
        found = set(Role.objects.filter(id__in=value, company=company).values_list("id", flat=True))
        missing = [str(role_id) for role_id in value if role_id not in found]
        if missing:
            raise serializers.ValidationError(f"Unknown role(s): {', '.join(missing)}.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value: str) -> str:
        user = self.context["request"].user
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": ["The current password is not correct."]})
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": ["The new password must be different from the current one."]}
            )
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PermissionDefSerializer(serializers.Serializer):
    code = serializers.CharField()
    module = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()

    @staticmethod
    def catalogue() -> list[dict[str, str]]:
        return [
            {"code": p.code, "module": p.module, "label": p.label, "description": p.description}
            for p in PERMISSIONS
        ]


class SessionSerializer(serializers.Serializer):
    """Everything the interface needs to render itself for the signed-in user."""

    user = UserSerializer(read_only=True)
    company = CompanyBrandingSerializer(read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
    must_change_password = serializers.BooleanField(read_only=True)


class HealthSerializer(serializers.Serializer):
    """Liveness probe response. Deliberately carries no configuration detail."""

    status = serializers.ChoiceField(choices=["ok", "degraded"], read_only=True)
    time = serializers.DateTimeField(read_only=True)


class ServiceStatusSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    detail = serializers.CharField(read_only=True)


class SystemStatusSerializer(serializers.Serializer):
    """Operator-facing readiness detail, gated on ``settings.view``."""

    client_code = serializers.CharField(read_only=True)
    release = serializers.CharField(read_only=True)
    debug = serializers.BooleanField(read_only=True)
    database = serializers.DictField(read_only=True)
    email = serializers.DictField(read_only=True)
    attachment_scanning = serializers.DictField(read_only=True)
    private_storage_root = serializers.CharField(read_only=True)


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "actor_label",
            "action",
            "entity_type",
            "entity_id",
            "entity_label",
            "summary",
            "changes",
            "request_id",
            "ip_address",
            "source",
        ]
        read_only_fields = fields


class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleSummarySerializer(read_only=True)

    class Meta:
        model = UserRole
        fields = ["id", "role", "granted_at"]
        read_only_fields = fields
