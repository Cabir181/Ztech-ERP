"""Role administration and the company settings screen."""

from __future__ import annotations

import pytest

from ztech_sales.core.models import AuditEvent, Role
from ztech_sales.core.permissions import ALL_PERMISSION_CODES

pytestmark = pytest.mark.django_db


def test_roles_are_listed_with_their_permissions_and_usage(signed_in, admin_user, rep_user):
    client = signed_in(admin_user)
    response = client.get("/api/roles/")
    assert response.status_code == 200
    by_code = {row["code"]: row for row in response.json()["results"]}
    assert by_code["sales_representative"]["assigned_user_count"] == 1
    assert "quotation.view.own" in by_code["sales_representative"]["permissions"]


def test_the_permission_catalogue_matches_the_codes_roles_may_hold(signed_in, admin_user):
    client = signed_in(admin_user)
    catalogue = client.get("/api/system/permissions/").json()
    assert {entry["code"] for entry in catalogue} == set(ALL_PERMISSION_CODES)
    assert all(entry["label"] and entry["description"] for entry in catalogue)


def test_creating_a_role_records_the_permissions_it_grants(signed_in, admin_user, company, csrf):
    client = signed_in(admin_user)
    response = client.post(
        "/api/roles/",
        {
            "code": "inside_sales",
            "name": "Inside Sales",
            "description": "Quotes only, no approvals.",
            "permissions": ["customer.view", "quotation.view.own", "quotation.create"],
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 201, response.json()
    role = Role.objects.get(company=company, code="inside_sales")
    assert role.permission_codes == ["customer.view", "quotation.create", "quotation.view.own"]
    assert role.is_system is False

    entry = AuditEvent.objects.get(action="role.created", entity_id=role.id)
    assert entry.changes["permissions"]["to"] == role.permission_codes


def test_an_unknown_permission_code_is_refused(signed_in, admin_user, csrf):
    client = signed_in(admin_user)
    response = client.post(
        "/api/roles/",
        {"code": "bad_role", "name": "Bad", "permissions": ["quotation.delete_everything"]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 400
    assert "permissions" in response.json()["error"]["details"]


def test_a_builtin_role_cannot_be_renamed_by_code_or_deactivated(signed_in, admin_user, roles, csrf):
    client = signed_in(admin_user)
    role = roles["approver"]
    version = client.get(f"/api/roles/{role.id}/").json()["version"]

    renamed = client.patch(
        f"/api/roles/{role.id}/",
        {"code": "something_else", "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert renamed.status_code == 400

    deactivated = client.patch(
        f"/api/roles/{role.id}/",
        {"is_active": False, "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert deactivated.status_code == 422


def test_editing_a_role_changes_what_its_holders_may_do(
    signed_in, admin_user, rep_user, roles, company, csrf
):
    client = signed_in(admin_user)
    role = roles["sales_representative"]
    version = client.get(f"/api/roles/{role.id}/").json()["version"]

    response = client.patch(
        f"/api/roles/{role.id}/",
        {"permissions": ["customer.view"], "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 200

    rep_user.clear_permission_cache()
    assert rep_user.get_permission_codes(company) == frozenset({"customer.view"})


def test_a_stale_role_update_is_refused_with_409(signed_in, admin_user, roles, csrf):
    client = signed_in(admin_user)
    role = roles["read_only"]
    version = client.get(f"/api/roles/{role.id}/").json()["version"]

    assert (
        client.patch(
            f"/api/roles/{role.id}/",
            {"description": "First edit", "version": version},
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
        ).status_code
        == 200
    )
    conflicted = client.patch(
        f"/api/roles/{role.id}/",
        {"description": "Second edit", "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert conflicted.status_code == 409


def test_role_management_is_refused_without_the_permission(signed_in, manager_user, roles, csrf):
    client = signed_in(manager_user)
    # A sales manager may read roles but not change what they grant.
    assert client.get("/api/roles/").status_code == 200
    response = client.patch(
        f"/api/roles/{roles['read_only'].id}/",
        {"description": "Nope", "version": 1},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 403


def test_company_settings_are_readable_and_editable_with_the_right_permission(
    signed_in, admin_user, company, csrf
):
    client = signed_in(admin_user)
    detail = client.get("/api/company/").json()
    assert detail["currency"]["code"] == "OMR"
    assert detail["currency"]["decimal_places"] == 3
    assert detail["timezone"] == "Asia/Muscat"

    response = client.patch(
        "/api/company/",
        {
            "trade_name": "Test Trading Co",
            "document_footer": "Thank you for your business.",
            "version": detail["version"],
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 200
    company.refresh_from_db()
    assert company.trade_name == "Test Trading Co"
    assert AuditEvent.objects.filter(action="company.updated").exists()


def test_company_settings_are_read_only_for_a_viewer(signed_in, viewer_user, csrf):
    client = signed_in(viewer_user)
    assert client.get("/api/company/").status_code == 200
    response = client.patch(
        "/api/company/",
        {"trade_name": "Hijacked", "version": 1},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 403


def test_an_invalid_timezone_is_refused(signed_in, admin_user, csrf):
    client = signed_in(admin_user)
    version = client.get("/api/company/").json()["version"]
    response = client.patch(
        "/api/company/",
        {"timezone": "Mars/Olympus_Mons", "version": version},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 400
