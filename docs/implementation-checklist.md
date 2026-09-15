# Implementation checklist

Maps every requirement to the increment that delivers it, the code that
implements it, the test that proves it, and its status.

**FR01–FR23 and AT01–AT32 are defined in `Sales_Module_Specification.md`, which
is not present in this workspace.** Their rows below are therefore marked
`BLOCKED — specification missing` rather than being invented. Filling them in
from guesswork would produce a checklist that looks complete and means nothing.
See [`progress.md`](progress.md) §1.

Status values: **Done** · **Partial** · **Not started** · **BLOCKED** · **NOT RUN**

---

## Increment A — foundation

Delivered in full. Every row was executed, not assumed.

| # | Requirement (from the technical baseline) | Code | Test | Status |
|---|---|---|---|---|
| A01 | Python 3.12, Django 5.2 LTS latest patch, DRF, PostgreSQL 16 | `backend/pyproject.toml` (Django 5.2.17, DRF 3.18.1) | `scripts/dev.sh check` | Done |
| A02 | Dependency versions verified and pinned in a lockfile | `backend/uv.lock`, `frontend/package-lock.json` | Docker build uses `uv sync --frozen` | Done |
| A03 | Modular backend packages | `backend/ztech_sales/{core,customers,catalog,pricing,sales,approvals,communications,reports,integrations}/` | `manage.py check` | Done (only `core` populated) |
| A04 | Runnable environment against real PostgreSQL | `docker-compose.yml`, `scripts/dev.sh` | Suite runs on PostgreSQL 16 | Done |
| A05 | Migrations | `core/migrations/0001_initial.py` | Applied in every test run | Done |
| A06 | Email sign-in with password | `core/auth_backends.py`, `core/api/views.py::LoginView` | `test_auth_api.py` | Done |
| A07 | Session authentication, same origin, CSRF on every mutation | `config/settings/base.py`, `config/urls.py`, `core/views.py::spa_index` | `test_security.py::test_mutations_are_refused_without_a_csrf_token` | Done |
| A08 | CSRF protection on sign-in itself | `LoginView` decorated with `csrf_protect` | `test_login_without_a_csrf_token_is_refused` | Done |
| A09 | Account enumeration resistance | `LoginView._invalid_credentials`, dummy hash on miss | `test_wrong_password_and_unknown_account_are_indistinguishable` | Done |
| A10 | Failed-attempt lockout | `core/models/user.py::register_failed_login` | `test_repeated_failures_lock_the_account` | Done |
| A11 | Session fixation closed on sign-in | `django_login` rotates key and token | `test_login_rotates_the_session_key` | Done |
| A12 | Roles and permissions, enforced server-side | `core/permissions.py`, `core/api/permissions.py` | `test_permissions_model.py`, `test_security.py` | Done |
| A13 | Permission revocation takes effect immediately | `EmailBackend.get_user`, `get_permission_codes` | `test_deactivation_ends_access_on_an_open_session` | Done |
| A14 | Approval authority is separable from administration | `ADMINISTRATOR_EXCLUDED_PERMISSIONS` | `test_administrator_flag_does_not_confer_approval_authority` | Done |
| A15 | Company ownership on every business record | `core/models/base.py::CompanyOwnedModel` | `test_company_scoping_excludes_another_companys_rows` | Done |
| A16 | Company time zone drives date-sensitive rules | `core/models/company.py::today/localtime` | `test_dates_are_evaluated_in_the_company_zone_not_in_utc` | Done |
| A17 | Decimal money, currency precision, OMR = 3 places | `core/money.py`, `Currency.decimal_places` | `test_money.py` (13 tests) | Done |
| A18 | Optimistic row versions; stale save returns 409 | `core/models/base.py::VersionedModel` | `test_a_stale_version_is_refused_with_409`, `test_concurrency.py` | Done |
| A19 | Protected fields cannot be written directly | serializer `read_only_fields`, service layer | `test_protected_fields_cannot_be_written_directly` | Done |
| A20 | Gap-free document numbering under concurrency | `core/models/sequence.py` | `test_a_document_sequence_never_issues_the_same_number_twice` | Done |
| A21 | Immutable audit trail | `core/models/audit.py`, `core/services/audit.py` | `test_audit_entries_cannot_be_modified_or_deleted` | Done |
| A22 | Secrets never reach the audit trail | `REDACTED_FIELDS` | `test_passwords_are_never_present_in_the_audit_trail` | Done |
| A23 | Durable database outbox, at-least-once, idempotent | `core/models/outbox.py`, `core/outbox_handlers.py` | `test_outbox.py` (11 tests) | Done |
| A24 | Concurrent workers never double-claim | `claim_batch` with `SKIP LOCKED` | `test_two_workers_never_claim_the_same_outbox_message` | Done |
| A25 | Isolated private attachment storage per client | `core/storage.py`, `MEDIA_ROOT = PRIVATE_STORAGE_ROOT/CLIENT_CODE` | `test_client_isolation.py` (18 tests) | Done |
| A26 | Attachments have no public URL | `PrivateStorage.url()` raises | `test_private_storage_refuses_to_produce_a_public_url` | Done |
| A27 | Path traversal and hostile filenames refused | `resolve_private_path`, `sanitise_filename` | `test_path_traversal_is_refused_not_clamped` | Done |
| A28 | Isolated client setup, one command | `bootstrap_client`, `create_admin` | Exercised by every test fixture | Done |
| A29 | Honest configuration status; no fake email success | `SystemStatusView`, no console-backend fallback | `test_system_status_...reports_email_honestly` | Done |
| A30 | Production refuses the development scan stub | `config/settings/prod.py` | Reviewed; see note below | Done |
| A31 | Docker Compose: web, worker, PostgreSQL, test inbox | `docker-compose.yml`, `deploy/Dockerfile` | See [`testing.md`](testing.md) | Done (build **NOT RUN** here) |
| A32 | Secrets supplied through the environment only | `config/env.py`, `.env.example` | `prod.py` raises without them | Done |
| A33 | OpenAPI schema with no generation warnings | `drf-spectacular`, `docs/api/openapi.yaml` | `./scripts/dev.sh schema` (`--fail-on-warn`) | Done |
| A34 | Original interface, permission-aware, keyboard operable | `frontend/src/` | `tests/browser/admin.spec.ts` | Done |
| A35 | Every displayed action works against the backend | `frontend/src/api/client.ts` | Browser tests write real records | Done |

> **A30 note.** The guard is a module-level `raise` in `config/settings/prod.py`,
> verified by reading the code, not by a test that imports production settings.
> A test for it would need a fully populated production environment; it is worth
> adding when the deployment pipeline exists.

---

## Increments B to F

| Increment | Scope | Status |
|---|---|---|
| B | Customers, addresses, products, taxes, terms, pricelists, templates | **BLOCKED — specification missing** |
| C | Quotation lists and forms, optional lines, Decimal calculation, price override, draft PDF preview | **BLOCKED — specification missing** (section 6 arithmetic) |
| D | Approval triggers and segregation, immutable issue snapshots, revision replacement, acceptance, confirmation, cancellation, transactional events | **BLOCKED — specification missing** |
| E | Customer PDFs, private attachments, scan adapter, email outbox, failure states, activities | **BLOCKED — specification missing** |
| F | Reporting and drill-down, safe CSV exports, integration contract, load fixture, operations docs | **BLOCKED — specification missing** |

---

## FR01–FR23

| Requirement | Status |
|---|---|
| FR01 … FR23 | **BLOCKED — specification missing.** The requirement text is in `Sales_Module_Specification.md`, which is not in this workspace. |

## AT01–AT32

| Acceptance test | Status |
|---|---|
| AT01 | **BLOCKED — specification missing.** The expected figures are quoted in the brief (900.000 net, 45.000 tax, 945.000 total, OMR). The inputs and the formula that produce them are in section 6. The Decimal foundation those figures depend on is implemented and tested (`test_money.py::test_omr_uses_three_decimal_places`). |
| AT02 … AT32 | **BLOCKED — specification missing.** |

---

## Cross-cutting requirements from the brief

| Requirement | Status | Where |
|---|---|---|
| Server recalculates totals; frontend is convenience only | Foundation done, arithmetic blocked | `core/money.py`; services own all writes |
| Never label order value as revenue, receivables or cash | Not yet applicable | No reports exist yet; constraint recorded in `architecture-decisions.md` |
| Integration events at-least-once with event IDs | Transport done, contract blocked | `core/models/outbox.py` |
| Two independent client environments with distinct credentials and storage | Storage isolation proven by test; two live environments **NOT RUN** | `test_client_isolation.py`, [`client-onboarding.md`](client-onboarding.md) |
| Backup and restore verified | **NOT RUN** | Procedure in [`backup-restore.md`](backup-restore.md) |
| CSV formula neutralisation | Not started (increment F) | — |
| Spoofed upload handling | Not started (increment E) | — |
| Performance fixture with observed results | **NOT RUN** | [`testing.md`](testing.md) §5 |
