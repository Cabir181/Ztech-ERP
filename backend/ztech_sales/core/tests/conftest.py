"""Shared fixtures.

The suite runs against a real PostgreSQL database. Several behaviours under test
- row locking with ``SELECT ... FOR UPDATE``, ``SKIP LOCKED`` claiming and
``NUMERIC`` arithmetic - do not exist or behave differently on SQLite, so a
green run on SQLite would prove nothing about the deployed system.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from ztech_sales.core.models import Company, Role, User, UserRole
from ztech_sales.core.permissions import (
    APPROVER,
    READ_ONLY,
    SALES_MANAGER,
    SALES_REPRESENTATIVE,
    SYSTEM_ADMINISTRATOR,
)

PASSWORD = "Test-Passw0rd-For-Suite!"


@pytest.fixture
def company(db) -> Company:
    call_command(
        "bootstrap_client",
        code="testco",
        legal_name="Test Trading LLC",
        trade_name="Test Trading",
        currency="OMR",
        timezone="Asia/Muscat",
        verbosity=0,
    )
    return Company.objects.select_related("currency").get(code="testco")


@pytest.fixture
def roles(company) -> dict[str, Role]:
    return {role.code: role for role in Role.objects.filter(company=company)}


def _make_user(company, roles, *, email, name, role_codes, **extra) -> User:
    user = User.objects.create_user(email=email, full_name=name, password=PASSWORD, **extra)
    for code in role_codes:
        UserRole.objects.create(user=user, role=roles[code])
    return user


@pytest.fixture
def admin_user(company, roles) -> User:
    return _make_user(
        company,
        roles,
        email="admin@testco.example",
        name="Ada Administrator",
        role_codes=[SYSTEM_ADMINISTRATOR],
        is_system_administrator=True,
    )


@pytest.fixture
def manager_user(company, roles) -> User:
    return _make_user(
        company, roles, email="manager@testco.example", name="Mo Manager", role_codes=[SALES_MANAGER]
    )


@pytest.fixture
def rep_user(company, roles) -> User:
    return _make_user(
        company,
        roles,
        email="rep@testco.example",
        name="Rae Representative",
        role_codes=[SALES_REPRESENTATIVE],
    )


@pytest.fixture
def second_rep_user(company, roles) -> User:
    return _make_user(
        company, roles, email="rep2@testco.example", name="Sam Second", role_codes=[SALES_REPRESENTATIVE]
    )


@pytest.fixture
def approver_user(company, roles) -> User:
    """Holds approval authority in addition to a sales role, as a real approver does."""
    return _make_user(
        company,
        roles,
        email="approver@testco.example",
        name="Ali Approver",
        role_codes=[SALES_REPRESENTATIVE, APPROVER],
    )


@pytest.fixture
def viewer_user(company, roles) -> User:
    return _make_user(
        company, roles, email="viewer@testco.example", name="Val Viewer", role_codes=[READ_ONLY]
    )


@pytest.fixture
def api() -> APIClient:
    """An unauthenticated client with CSRF enforcement switched on.

    CSRF is enforced in tests exactly as in production, so a test that mutates
    data has to obtain and send a token the same way the browser does.
    """
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def signed_in(api):
    """Return a helper that signs a user in through the real login endpoint."""

    def _sign_in(user: User, password: str = PASSWORD) -> APIClient:
        api.get("/api/auth/csrf/")
        token = api.cookies["ztech_csrftoken"].value
        response = api.post(
            "/api/auth/login/",
            {"email": user.email, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 200, response.data
        api.csrf_token = api.cookies["ztech_csrftoken"].value
        return api

    return _sign_in


@pytest.fixture
def csrf():
    """Extract the current CSRF token from a client's cookie jar."""

    def _token(client: APIClient) -> str:
        return client.cookies["ztech_csrftoken"].value

    return _token
