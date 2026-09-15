"""Core API: authentication, session, company settings, users, roles and audit."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.db import connection, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ztech_sales.core.api.permissions import HasCompanyPermission
from ztech_sales.core.api.serializers import (
    AuditEventSerializer,
    CompanySerializer,
    HealthSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PermissionDefSerializer,
    RoleSerializer,
    SessionSerializer,
    SystemStatusSerializer,
    UserSerializer,
    UserWriteSerializer,
)
from ztech_sales.core.middleware import client_ip
from ztech_sales.core.models import AuditEvent, Company, Role, User
from ztech_sales.core.services.audit import build_change_set, record_audit
from ztech_sales.core.services.identity import (
    change_own_password,
    create_role,
    create_user,
    update_role,
    update_user,
)
from ztech_sales.core.tenancy import get_active_company

AUTH_BACKEND = "ztech_sales.core.auth_backends.EmailBackend"


def _session_payload(request: Request) -> dict[str, Any]:
    from ztech_sales.core.api.serializers import CompanyBrandingSerializer

    company = get_active_company(request)
    user = request.user
    return {
        "user": UserSerializer(user).data,
        "company": CompanyBrandingSerializer(company).data,
        "permissions": sorted(user.get_permission_codes(company)),
        "must_change_password": user.must_change_password,
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    """Issue the CSRF cookie the interface echoes back in ``X-CSRFToken``."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: OpenApiResponse(description="CSRF cookie set.")})
    def get(self, request: Request) -> Response:
        return Response({"detail": "CSRF cookie set."})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Sign in with an email address and password.

    CSRF protection is applied explicitly: DRF exempts unauthenticated requests
    by default, which would leave the login form open to a login-CSRF attack.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(request=LoginSerializer, responses={200: SessionSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        user = User.objects.filter(email=email).first()
        if user is None:
            # Equalise response time so a missing account cannot be told apart
            # from a wrong password.
            User().set_password(password)
            return self._invalid_credentials()

        if not user.check_password(password):
            if user.is_active:
                user.register_failed_login(settings.LOGIN_MAX_FAILED_ATTEMPTS, settings.LOGIN_LOCKOUT_SECONDS)
            return self._invalid_credentials()

        # Beyond this point the caller has proved they hold the password, so a
        # specific reason can be given without helping an attacker.
        if not user.is_active:
            return Response(
                {
                    "error": {
                        "code": "account_inactive",
                        "message": "This account has been deactivated. Contact your administrator.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.is_locked:
            return Response(
                {
                    "error": {
                        "code": "account_locked",
                        "message": "Too many failed sign-in attempts. Try again later.",
                        "details": {"locked_until": user.locked_until.isoformat()},
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # django_login cycles the session key and rotates the CSRF token, which
        # closes session fixation.
        django_login(request, user, backend=AUTH_BACKEND)
        user.register_successful_login(client_ip(request))

        company = get_active_company(request)
        record_audit(
            company=company,
            action="auth.signed_in",
            entity_type="core.user",
            entity_id=user.id,
            entity_label=user.full_name,
            summary=f"{user.email} signed in.",
            actor=user,
        )
        return Response(_session_payload(request))

    @staticmethod
    def _invalid_credentials() -> Response:
        return Response(
            {
                "error": {
                    "code": "invalid_credentials",
                    "message": "Email address or password is not correct.",
                }
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Signed out.")})
    def post(self, request: Request) -> Response:
        user = request.user
        company = get_active_company(request)
        record_audit(
            company=company,
            action="auth.signed_out",
            entity_type="core.user",
            entity_id=user.id,
            entity_label=user.full_name,
            summary=f"{user.email} signed out.",
            actor=user,
        )
        django_logout(request)
        return Response({"detail": "Signed out."})


class SessionView(APIView):
    """Who is signed in, what they may do, and how to brand the interface."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SessionSerializer})
    def get(self, request: Request) -> Response:
        return Response(_session_payload(request))


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={200: OpenApiResponse(description="Changed.")})
    def post(self, request: Request) -> Response:
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        company = get_active_company(request)
        change_own_password(
            company=company, user=request.user, new_password=serializer.validated_data["new_password"]
        )
        # Keep the current session usable after the password change.
        django_login(request, request.user, backend=AUTH_BACKEND)
        return Response({"detail": "Password changed."})


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class HealthView(APIView):
    """Liveness probe. Deliberately reveals nothing about the configuration."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: HealthSerializer, 503: HealthSerializer})
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database_ok = True
        except Exception:  # noqa: BLE001 - probe must answer, not raise
            database_ok = False
        payload = {"status": "ok" if database_ok else "degraded", "time": timezone.now().isoformat()}
        return Response(payload, status=200 if database_ok else 503)


class SystemStatusView(APIView):
    """Honest readiness detail for an operator.

    Email in particular is reported as ``not_configured`` when no SMTP host is
    set. The application never reports a message as sent because a console
    backend accepted it.
    """

    permission_classes = [IsAuthenticated, HasCompanyPermission]
    required_permissions = ["settings.view"]

    @extend_schema(responses={200: SystemStatusSerializer})
    def get(self, request: Request) -> Response:
        email_configured = bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL)
        scanner = settings.ATTACHMENT_SCANNER
        return Response(
            {
                "client_code": settings.CLIENT_CODE,
                "release": "1.0.0",
                "debug": settings.DEBUG,
                "database": {"engine": "postgresql", "connected": True},
                "email": {
                    "status": "configured" if email_configured else "not_configured",
                    "host": settings.EMAIL_HOST or None,
                    "from_address": settings.DEFAULT_FROM_EMAIL or None,
                    "detail": (
                        "Outbound email is configured."
                        if email_configured
                        else "EMAIL_HOST and DEFAULT_FROM_EMAIL are not set; email cannot be sent "
                        "and will not be reported as sent."
                    ),
                },
                "attachment_scanning": {
                    "adapter": scanner,
                    "status": "development_stub" if scanner == "stub" else "configured",
                    "detail": (
                        "The stub adapter accepts uploads without scanning and is refused in "
                        "production settings."
                        if scanner == "stub"
                        else "Uploads are scanned before they are stored."
                    ),
                },
                "private_storage_root": str(settings.MEDIA_ROOT),
            }
        )


class PermissionCatalogueView(APIView):
    """The full permission catalogue, used to build the role editor."""

    permission_classes = [IsAuthenticated, HasCompanyPermission]
    required_permissions = ["role.view"]

    @extend_schema(responses={200: PermissionDefSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(PermissionDefSerializer.catalogue())


# ---------------------------------------------------------------------------
# Company settings
# ---------------------------------------------------------------------------


class CompanyView(APIView):
    """The company this deployment serves. There is exactly one."""

    permission_classes = [IsAuthenticated, HasCompanyPermission]
    required_permissions = {
        "get": ["settings.view"],
        "patch": ["settings.manage"],
        "default": ["settings.view"],
    }

    @extend_schema(responses={200: CompanySerializer})
    def get(self, request: Request) -> Response:
        company = get_active_company(request)
        return Response(CompanySerializer(company).data)

    @extend_schema(request=CompanySerializer, responses={200: CompanySerializer})
    def patch(self, request: Request) -> Response:
        active = get_active_company(request)
        with transaction.atomic():
            company = Company.objects.select_for_update().get(pk=active.pk)
            company.assert_version(request.data.get("version"))
            before = CompanySerializer(company).data

            serializer = CompanySerializer(company, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            company = serializer.save()
            company.full_clean(exclude=["currency"])
            company.save()

            after = CompanySerializer(company).data
            changes = build_change_set(before, after)
            changes.pop("version", None)
            if changes:
                record_audit(
                    company=company,
                    action="company.updated",
                    entity_type="core.company",
                    entity_id=company.id,
                    entity_label=company.display_name,
                    summary="Updated company settings.",
                    changes=changes,
                    actor=request.user,
                )
        return Response(CompanySerializer(company).data)


# ---------------------------------------------------------------------------
# Users and roles
# ---------------------------------------------------------------------------


class UserViewSet(viewsets.ModelViewSet):
    """User administration.

    Accounts are never deleted: history must keep naming the person who acted.
    Deactivating an account removes access immediately, including on a session
    that is already open.
    """

    permission_classes = [IsAuthenticated, HasCompanyPermission]
    required_permissions = {
        "list": ["user.view"],
        "retrieve": ["user.view"],
        "create": ["user.manage"],
        "update": ["user.manage"],
        "partial_update": ["user.manage"],
        # ``me`` is reachable by any signed-in user, not only by user administrators.
        "me": [],
        "default": ["user.manage"],
    }
    serializer_class = UserSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        company = get_active_company(self.request)
        queryset = User.objects.prefetch_related("role_assignments_set__role").order_by("full_name")

        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q

            queryset = queryset.filter(Q(full_name__icontains=search) | Q(email__icontains=search))

        is_active = self.request.query_params.get("is_active")
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=is_active == "true")

        role_code = self.request.query_params.get("role")
        if role_code:
            queryset = queryset.filter(
                role_assignments_set__role__code=role_code, role_assignments_set__role__company=company
            )
        return queryset.distinct()

    def get_serializer_context(self) -> dict[str, Any]:
        context = super().get_serializer_context()
        context["company"] = get_active_company(self.request)
        return context

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company = get_active_company(request)
        serializer = UserWriteSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        user = create_user(company=company, data=dict(serializer.validated_data), actor=request.user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company = get_active_company(request)
        instance = self.get_object()
        serializer = UserWriteSerializer(
            instance,
            data=request.data,
            partial=kwargs.get("partial", False),
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        payload["version"] = request.data.get("version")
        user = update_user(company=company, user_id=instance.pk, data=payload, actor=request.user)
        return Response(UserSerializer(user).data)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request: Request) -> Response:
        return Response(_session_payload(request))


class RoleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasCompanyPermission]
    required_permissions = {
        "list": ["role.view"],
        "retrieve": ["role.view"],
        "create": ["role.manage"],
        "update": ["role.manage"],
        "partial_update": ["role.manage"],
        "default": ["role.manage"],
    }
    serializer_class = RoleSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        from django.db.models import Count

        company = get_active_company(self.request)
        return (
            Role.objects.for_company(company)
            .prefetch_related("role_permissions")
            .annotate(assigned_user_count=Count("assignments", distinct=True))
            .order_by("name")
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company = get_active_company(request)
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = create_role(company=company, data=dict(serializer.validated_data), actor=request.user)
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        company = get_active_company(request)
        instance = self.get_object()
        serializer = RoleSerializer(instance, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        payload["version"] = request.data.get("version")
        role = update_role(company=company, role_id=instance.pk, data=payload, actor=request.user)
        return Response(RoleSerializer(role).data)


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only view of the immutable audit trail."""

    permission_classes = [IsAuthenticated, HasCompanyPermission]
    required_permissions = ["audit.view"]
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        company = get_active_company(self.request)
        queryset = AuditEvent.objects.filter(company=company)

        params = self.request.query_params
        if params.get("entity_type"):
            queryset = queryset.filter(entity_type=params["entity_type"])
        if params.get("entity_id"):
            queryset = queryset.filter(entity_id=params["entity_id"])
        if params.get("action"):
            queryset = queryset.filter(action=params["action"])
        if params.get("actor_id"):
            queryset = queryset.filter(actor_id=params["actor_id"])
        return queryset
