"""Authentication, session handling and CSRF."""

from __future__ import annotations

import pytest
from django.utils import timezone

from ztech_sales.core.models import AuditEvent, User
from ztech_sales.core.tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _csrf(api):
    api.get("/api/auth/csrf/")
    return api.cookies["ztech_csrftoken"].value


def test_csrf_endpoint_sets_the_cookie(api):
    response = api.get("/api/auth/csrf/")
    assert response.status_code == 200
    assert "ztech_csrftoken" in response.cookies


def test_login_without_a_csrf_token_is_refused(api, rep_user):
    response = api.post("/api/auth/login/", {"email": rep_user.email, "password": PASSWORD}, format="json")
    # Login itself is CSRF protected: DRF exempts unauthenticated requests by
    # default, which would otherwise leave the sign-in form open to login CSRF.
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_login_succeeds_and_returns_the_session_payload(api, rep_user, company):
    token = _csrf(api)
    response = api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == rep_user.email
    assert body["company"]["currency_code"] == "OMR"
    assert body["company"]["decimal_places"] == 3
    assert "quotation.view.own" in body["permissions"]
    assert "quotation.view.all" not in body["permissions"]


def test_login_is_case_insensitive_on_the_email_address(api, rep_user):
    token = _csrf(api)
    response = api.post(
        "/api/auth/login/",
        {"email": rep_user.email.upper(), "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200


def test_wrong_password_and_unknown_account_are_indistinguishable(api, rep_user):
    token = _csrf(api)
    wrong = api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": "not-the-password"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    unknown = api.post(
        "/api/auth/login/",
        {"email": "nobody@testco.example", "password": "not-the-password"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_repeated_failures_lock_the_account(api, rep_user, settings):
    settings.LOGIN_MAX_FAILED_ATTEMPTS = 3
    token = _csrf(api)
    for _ in range(3):
        api.post(
            "/api/auth/login/",
            {"email": rep_user.email, "password": "wrong"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
    rep_user.refresh_from_db()
    assert rep_user.is_locked

    response = api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    # The real reason is only disclosed to a caller who proved they hold the
    # password; a guesser still sees "invalid credentials".
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_locked"


def test_a_successful_sign_in_clears_the_failure_counter(api, rep_user):
    token = _csrf(api)
    api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": "wrong"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    rep_user.refresh_from_db()
    assert rep_user.failed_login_count == 1

    api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    rep_user.refresh_from_db()
    assert rep_user.failed_login_count == 0
    assert rep_user.last_login is not None


def test_a_deactivated_account_cannot_sign_in(api, rep_user):
    rep_user.is_active = False
    rep_user.save()
    token = _csrf(api)
    response = api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


def test_deactivation_ends_access_on_an_open_session(signed_in, rep_user):
    client = signed_in(rep_user)
    assert client.get("/api/auth/session/").status_code == 200

    rep_user.is_active = False
    rep_user.save()

    # Revoking access takes effect on the very next request, not when the
    # session cookie eventually expires.
    assert client.get("/api/auth/session/").status_code == 403


def test_login_rotates_the_session_key(api, rep_user):
    api.get("/api/auth/csrf/")
    token = api.cookies["ztech_csrftoken"].value
    api.get("/api/system/health/")
    before = api.cookies.get("ztech_sessionid")
    before_value = before.value if before else None

    api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    after = api.cookies["ztech_sessionid"].value
    assert after != before_value


def test_sign_in_and_sign_out_are_both_audited(signed_in, rep_user, company, csrf):
    client = signed_in(rep_user)
    client.post("/api/auth/logout/", format="json", HTTP_X_CSRFTOKEN=csrf(client))

    actions = list(
        AuditEvent.objects.filter(company=company, actor=rep_user).values_list("action", flat=True)
    )
    assert "auth.signed_in" in actions
    assert "auth.signed_out" in actions


def test_session_requires_authentication(api):
    assert api.get("/api/auth/session/").status_code == 403


def test_password_change_requires_the_current_password(signed_in, rep_user, csrf):
    client = signed_in(rep_user)
    response = client.post(
        "/api/auth/password/",
        {"current_password": "wrong", "new_password": "An0ther-Str0ng-Passw0rd!"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 400
    assert "current_password" in response.json()["error"]["details"]


def test_password_change_enforces_the_password_policy(signed_in, rep_user, csrf):
    client = signed_in(rep_user)
    response = client.post(
        "/api/auth/password/",
        {"current_password": PASSWORD, "new_password": "short"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 400
    assert "new_password" in response.json()["error"]["details"]


def test_password_change_succeeds_and_keeps_the_session_usable(signed_in, rep_user, csrf):
    client = signed_in(rep_user)
    new_password = "An0ther-Str0ng-Passw0rd!"
    response = client.post(
        "/api/auth/password/",
        {"current_password": PASSWORD, "new_password": new_password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 200
    assert client.get("/api/auth/session/").status_code == 200

    rep_user.refresh_from_db()
    assert rep_user.check_password(new_password)
    assert rep_user.must_change_password is False


def test_health_endpoint_is_public_and_reveals_nothing(api):
    response = api.get("/api/system/health/")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "time"}


def test_system_status_requires_a_permission_and_reports_email_honestly(signed_in, admin_user, settings):
    settings.EMAIL_HOST = ""
    client = signed_in(admin_user)
    response = client.get("/api/system/status/")
    assert response.status_code == 200
    # No console-backend fallback that would let the application claim a message
    # was sent when nothing can be delivered.
    assert response.json()["email"]["status"] == "not_configured"


def test_system_status_is_refused_without_the_permission(signed_in, rep_user):
    client = signed_in(rep_user)
    assert client.get("/api/system/status/").status_code == 403


def test_locked_account_unlocks_once_the_window_passes(api, rep_user):
    rep_user.locked_until = timezone.now() - timezone.timedelta(seconds=1)
    rep_user.save()
    assert User.objects.get(pk=rep_user.pk).is_locked is False
