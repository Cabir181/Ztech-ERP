"""User administration through the API."""

from __future__ import annotations

import pytest

from ztech_sales.core.models import AuditEvent, User, UserRole
from ztech_sales.core.permissions import SALES_REPRESENTATIVE

pytestmark = pytest.mark.django_db

NEW_USER = {
    "email": "new.person@testco.example",
    "full_name": "New Person",
    "job_title": "Sales Executive",
    "initial_password": "Initial-Str0ng-Passw0rd!",
}


def test_listing_users_requires_a_permission(signed_in, rep_user):
    client = signed_in(rep_user)
    response = client.get("/api/users/")
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "permission_denied"
    # The refusal names the permission that would have been sufficient, so an
    # administrator can act on a support call without reading the source.
    assert error["details"]["required_any_of"] == ["user.view"]


def test_manager_may_read_users_but_not_create_them(signed_in, manager_user, csrf):
    client = signed_in(manager_user)
    assert client.get("/api/users/").status_code == 200
    response = client.post("/api/users/", NEW_USER, format="json", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 403


def test_administrator_creates_a_user_with_roles(signed_in, admin_user, roles, company, csrf):
    client = signed_in(admin_user)
    payload = {**NEW_USER, "role_ids": [str(roles[SALES_REPRESENTATIVE].id)]}
    response = client.post("/api/users/", payload, format="json", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 201, response.json()

    created = User.objects.get(email=NEW_USER["email"])
    assert created.must_change_password is True
    assert [assignment.role.code for assignment in created.role_assignments_set.all()] == [
        SALES_REPRESENTATIVE
    ]
    assert created.has_permission("quotation.create", company)

    entry = AuditEvent.objects.get(action="user.created", entity_id=created.id)
    assert entry.actor == admin_user
    assert entry.changes["roles"]["to"] == [SALES_REPRESENTATIVE]


def test_a_weak_initial_password_is_refused(signed_in, admin_user, csrf):
    client = signed_in(admin_user)
    payload = {**NEW_USER, "initial_password": "password"}
    response = client.post("/api/users/", payload, format="json", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 400
    assert "initial_password" in response.json()["error"]["details"]


def test_duplicate_email_addresses_are_refused(signed_in, admin_user, rep_user, csrf):
    client = signed_in(admin_user)
    payload = {**NEW_USER, "email": rep_user.email.upper()}
    response = client.post("/api/users/", payload, format="json", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 400
    assert "email" in response.json()["error"]["details"]


def test_a_stale_version_is_refused_with_409(signed_in, admin_user, rep_user, csrf):
    client = signed_in(admin_user)
    detail = client.get(f"/api/users/{rep_user.id}/").json()
    stale_version = detail["version"]

    first = client.patch(
        f"/api/users/{rep_user.id}/",
        {"job_title": "Senior Sales Executive", "version": stale_version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert first.status_code == 200

    # A second user still holding the original copy must not overwrite the first
    # change without noticing it.
    second = client.patch(
        f"/api/users/{rep_user.id}/",
        {"job_title": "Account Manager", "version": stale_version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert second.status_code == 409
    body = second.json()["error"]
    assert body["code"] == "stale_object"
    assert body["details"]["submitted_version"] == stale_version

    rep_user.refresh_from_db()
    assert rep_user.job_title == "Senior Sales Executive"


def test_an_update_without_a_version_is_refused(signed_in, admin_user, rep_user, csrf):
    client = signed_in(admin_user)
    response = client.patch(
        f"/api/users/{rep_user.id}/",
        {"job_title": "No Version Supplied"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "business_rule_violated"


def test_an_administrator_cannot_deactivate_themselves(signed_in, admin_user, csrf):
    client = signed_in(admin_user)
    version = client.get(f"/api/users/{admin_user.id}/").json()["version"]
    response = client.patch(
        f"/api/users/{admin_user.id}/",
        {"is_active": False, "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 422
    assert "your own account" in response.json()["error"]["message"]


def test_an_administrator_cannot_drop_their_own_administrator_flag(signed_in, admin_user, csrf):
    client = signed_in(admin_user)
    version = client.get(f"/api/users/{admin_user.id}/").json()["version"]
    response = client.patch(
        f"/api/users/{admin_user.id}/",
        {"is_system_administrator": False, "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 422


def test_replacing_roles_removes_the_ones_left_out(signed_in, admin_user, rep_user, roles, company, csrf):
    client = signed_in(admin_user)
    version = client.get(f"/api/users/{rep_user.id}/").json()["version"]
    response = client.patch(
        f"/api/users/{rep_user.id}/",
        {"role_ids": [str(roles["read_only"].id)], "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 200
    codes = sorted(assignment.role.code for assignment in UserRole.objects.filter(user=rep_user))
    assert codes == ["read_only"]

    rep_user.clear_permission_cache()
    assert not rep_user.has_permission("quotation.create", company)


def test_an_unknown_role_id_is_refused(signed_in, admin_user, rep_user, csrf):
    import uuid

    client = signed_in(admin_user)
    version = client.get(f"/api/users/{rep_user.id}/").json()["version"]
    response = client.patch(
        f"/api/users/{rep_user.id}/",
        {"role_ids": [str(uuid.uuid4())], "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 400
    assert "role_ids" in response.json()["error"]["details"]


def test_users_cannot_be_deleted(signed_in, admin_user, rep_user, csrf):
    # History has to keep naming the person who acted, so accounts are
    # deactivated rather than removed.
    client = signed_in(admin_user)
    response = client.delete(f"/api/users/{rep_user.id}/", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 405


def test_me_is_available_to_any_signed_in_user(signed_in, rep_user):
    client = signed_in(rep_user)
    response = client.get("/api/users/me/")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == rep_user.email


def test_search_and_filters_narrow_the_list(signed_in, admin_user, rep_user, manager_user):
    client = signed_in(admin_user)
    by_name = client.get("/api/users/?search=Manager").json()
    assert [row["email"] for row in by_name["results"]] == [manager_user.email]

    by_role = client.get(f"/api/users/?role={SALES_REPRESENTATIVE}").json()
    assert {row["email"] for row in by_role["results"]} == {rep_user.email}


def test_the_roles_a_user_holds_are_returned_with_the_record(signed_in, admin_user, rep_user):
    # A read-only serializer field whose attribute is missing is silently
    # dropped by DRF rather than raising, so this asserts the payload itself.
    client = signed_in(admin_user)
    detail = client.get(f"/api/users/{rep_user.id}/").json()
    assert [role["code"] for role in detail["roles"]] == [SALES_REPRESENTATIVE]

    listed = client.get("/api/users/").json()["results"]
    assert all("roles" in row for row in listed)


def test_listing_users_does_not_scale_its_query_count_with_the_rows(
    signed_in, admin_user, rep_user, manager_user, viewer_user, django_assert_max_num_queries
):
    client = signed_in(admin_user)
    with django_assert_max_num_queries(12):
        assert client.get("/api/users/").status_code == 200


def test_the_password_is_never_returned(signed_in, admin_user, rep_user):
    client = signed_in(admin_user)
    body = client.get(f"/api/users/{rep_user.id}/").json()
    assert "password" not in body
    assert "initial_password" not in body
