"""Core API routes."""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ztech_sales.core.api import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("roles", views.RoleViewSet, basename="role")
router.register("audit-events", views.AuditEventViewSet, basename="audit-event")

urlpatterns = [
    path("auth/csrf/", views.CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/session/", views.SessionView.as_view(), name="auth-session"),
    path("auth/password/", views.PasswordChangeView.as_view(), name="auth-password"),
    path("system/health/", views.HealthView.as_view(), name="system-health"),
    path("system/status/", views.SystemStatusView.as_view(), name="system-status"),
    path("system/permissions/", views.PermissionCatalogueView.as_view(), name="system-permissions"),
    path("company/", views.CompanyView.as_view(), name="company"),
    path("", include(router.urls)),
]
