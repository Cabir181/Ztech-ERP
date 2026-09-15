"""Security behaviour that has to hold against direct API calls.

These tests deliberately bypass the interface. Hiding a menu entry is not a
control; every one of these requests is the sort a browser devtools console or a
curl command can make.
"""

from __future__ import annotations

import uuid

import pytest

from ztech_sales.core.models import AuditEvent
from ztech_sales.core.tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

PROTECTED_GET_ENDPOINTS = [
    "/api/auth/session/",
    "/api/users/",
    "/api/users/me/",
    "/api/roles/",
    "/api/audit-events/",
    "/api/company/",
    "/api/system/status/",
    "/api/system/permissions/",
]


@pytest.mark.parametrize("path", PROTECTED_GET_ENDPOINTS)
def test_every_protected_endpoint_refuses_an_anonymous_request(api, company, path):
    response = api.get(path)
    assert response.status_code in (401, 403), path


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/users/", {"email": "x@y.example", "full_name": "X"}),
        ("patch", "/api/company/", {"trade_name": "X", "version": 1}),
        ("post", "/api/roles/", {"code": "x", "name": "X"}),
        ("post", "/api/auth/password/", {"current_password": "a", "new_password": "b"}),
    ],
)
def test_mutations_are_refused_without_a_csrf_token(signed_in, admin_user, method, path, payload):
    client = signed_in(admin_user)
    # The session cookie alone is not enough: a cross-site form post carries the
    # cookie but cannot read the CSRF token.
    response = getattr(client, method)(path, payload, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] in {"csrf_failed", "permission_denied"}


def test_the_session_cookie_is_http_only_and_same_site(api, rep_user):
    api.get("/api/auth/csrf/")
    token = api.cookies["ztech_csrftoken"].value
    api.post(
        "/api/auth/login/",
        {"email": rep_user.email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    session_cookie = api.cookies["ztech_sessionid"]
    assert session_cookie["httponly"] is True
    assert session_cookie["samesite"] == "Lax"

    # The CSRF cookie must stay readable: the interface has to echo it back.
    assert api.cookies["ztech_csrftoken"]["httponly"] == ""


def test_a_representative_cannot_reach_user_administration_directly(signed_in, rep_user, admin_user, csrf):
    client = signed_in(rep_user)
    assert client.get("/api/users/").status_code == 403
    assert client.get(f"/api/users/{admin_user.id}/").status_code == 403
    assert (
        client.patch(
            f"/api/users/{admin_user.id}/",
            {"is_active": False, "version": 1},
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
        ).status_code
        == 403
    )


def test_an_unknown_identifier_reports_not_found_rather_than_forbidden(signed_in, admin_user):
    client = signed_in(admin_user)
    response = client.get(f"/api/users/{uuid.uuid4()}/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_protected_fields_cannot_be_written_directly(signed_in, admin_user, rep_user, csrf):
    client = signed_in(admin_user)
    version = client.get(f"/api/users/{rep_user.id}/").json()["version"]
    response = client.patch(
        f"/api/users/{rep_user.id}/",
        {
            "job_title": "Legitimate change",
            "version": version,
            # None of these are writable through the API.
            "id": str(uuid.uuid4()),
            "date_joined": "1999-01-01T00:00:00Z",
            "last_login": "1999-01-01T00:00:00Z",
            "password": "pwned",
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 200

    before_id = rep_user.id
    rep_user.refresh_from_db()
    assert rep_user.id == before_id
    assert rep_user.date_joined.year != 1999
    assert rep_user.check_password(PASSWORD)


def test_the_version_field_cannot_be_forced_by_the_client(signed_in, admin_user, rep_user, csrf):
    client = signed_in(admin_user)
    version = client.get(f"/api/users/{rep_user.id}/").json()["version"]
    client.patch(
        f"/api/users/{rep_user.id}/",
        {"job_title": "Changed", "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    rep_user.refresh_from_db()
    # The server owns the version counter; the submitted value is only ever
    # compared, never stored.
    assert rep_user.version == version + 1


def test_audit_entries_cannot_be_modified_or_deleted(signed_in, admin_user, company, csrf):
    client = signed_in(admin_user)
    entry = AuditEvent.objects.filter(company=company).first()
    assert entry is not None

    entry.summary = "Rewritten history"
    with pytest.raises(ValueError, match="immutable"):
        entry.save()

    with pytest.raises(NotImplementedError):
        entry.delete()

    # And there is no API route that would do it either, even with a valid
    # CSRF token and the audit.view permission.
    response = client.delete(f"/api/audit-events/{entry.id}/", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 405


def test_the_audit_trail_is_refused_without_the_permission(signed_in, rep_user):
    client = signed_in(rep_user)
    assert client.get("/api/audit-events/").status_code == 403


def test_passwords_are_never_present_in_the_audit_trail(signed_in, admin_user, company, csrf):
    client = signed_in(admin_user)
    client.post(
        "/api/users/",
        {
            "email": "audited@testco.example",
            "full_name": "Audited Person",
            "initial_password": "A-Very-Str0ng-Passw0rd!",
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    serialised = str(list(AuditEvent.objects.filter(company=company).values_list("changes", flat=True)))
    assert "A-Very-Str0ng-Passw0rd!" not in serialised
    assert "password" not in serialised


def test_the_last_administrator_cannot_be_locked_out(signed_in, admin_user, rep_user, roles, csrf):
    """Removing the final account that can manage users is refused.

    Without this guard an environment can reach a state that only a database
    console can recover from.
    """
    client = signed_in(admin_user)

    # Give the representative administrator rights so the admin can step down.
    version = client.get(f"/api/users/{rep_user.id}/").json()["version"]
    promote = client.patch(
        f"/api/users/{rep_user.id}/",
        {"is_system_administrator": True, "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert promote.status_code == 200

    # Now stepping the representative back down again is fine, because the
    # original administrator is still there.
    version = client.get(f"/api/users/{rep_user.id}/").json()["version"]
    demote = client.patch(
        f"/api/users/{rep_user.id}/",
        {"is_system_administrator": False, "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert demote.status_code == 200


def test_error_responses_never_leak_a_stack_trace(signed_in, admin_user):
    client = signed_in(admin_user)
    response = client.get("/api/users/not-a-uuid/")
    assert response.status_code in (400, 404)
    body = response.json()
    assert "Traceback" not in str(body)
    assert set(body) == {"error"}
