# Architecture decisions

Each entry records what was decided, why, and what it costs. Decisions are
appended, not rewritten; a superseded decision is marked and left in place so
that the reasoning at the time stays readable.

---

## ADR-001 — Django 5.2 LTS with DRF, not a lighter framework

**Decision.** Django 5.2 LTS (5.2.17) with Django REST Framework 3.18.1.

**Why.** The product needs migrations, transactions with explicit row locking,
session authentication with CSRF, and a permission model that survives an
upgrade. Django provides all of it with a long-term support window, which
matters for software sold to multiple clients who will not all upgrade on the
same day.

**Cost.** Django's ORM makes some reporting queries more awkward than raw SQL
would. Accepted: reporting queries can drop to `.raw()` where it is genuinely
warranted, and increment F will show whether any actually are.

---

## ADR-002 — Session authentication, same origin, not bearer tokens

**Decision.** Server-side sessions in a `HttpOnly` cookie, CSRF protection on
every mutation, and the compiled interface served by the same Django process.

**Why.** A token in `localStorage` is readable by any script that gets onto the
page. An `HttpOnly` cookie is not. Serving both from one origin removes CORS
entirely — there is no cross-origin configuration to get wrong, and no
preflight. Revocation is immediate, because the session lives in the database.

**Cost.** Horizontal scaling shares session state through the database rather
than being stateless. At this product's scale that is a non-issue, and it buys
instant revocation, which a stateless JWT cannot give without a blocklist that
reintroduces the shared state anyway.

**Note.** DRF exempts unauthenticated requests from CSRF by default. `LoginView`
is therefore decorated with `csrf_protect` explicitly, because otherwise the
sign-in form is open to login CSRF. `test_login_without_a_csrf_token_is_refused`
guards that.

---

## ADR-003 — Custom user model without `PermissionsMixin` and without Django admin

**Decision.** `core.User` extends `AbstractBaseUser` only. Django's permission
framework, groups, staff flag and admin site are not installed.

**Why.** Two permission systems disagreeing is worse than one. Authorisation is
answered entirely by this application's own role model, so there is exactly one
place to look when asking why someone was refused. Django admin also carries
Django's own branding and would be a second, unaudited write path into the
business data.

**Cost.** No `createsuperuser` and no free admin screens. `create_admin` and the
application's own screens replace them, and both write audit entries — which the
admin site would not have.

---

## ADR-004 — Permissions declared in code, roles stored in the database

**Decision.** The catalogue of permission codes lives in
`core/permissions.py`. Roles live in the database and reference those codes.

**Why.** Adding or retiring a permission is then a code change with no data
migration. Clients can still define their own roles, which they need. A role
holding a code this release no longer defines is ignored at resolution time
rather than granting anything, and `manage.py check_roles` reports it.

**Cost.** A client cannot invent a permission. That is deliberate: a permission
means nothing unless code enforces it.

---

## ADR-005 — Administrator flag does not confer approval authority

**Decision.** `is_system_administrator` grants every permission except
`approval.decide`.

**Why.** Segregation of duties. The person who administers the system is not
automatically the person who may approve a discount. Keeping approval authority
in the role assignments means "who may approve?" is always answerable from data,
which is what an auditor asks for. It is also the foundation the specification's
self-approval rule sits on.

**Cost.** A new environment has an administrator who cannot approve anything
until an Approver role is assigned. `create_admin` says so on completion.

---

## ADR-006 — Decimal everywhere, currency-driven precision, strings on the wire

**Decision.** All money is `decimal.Decimal` on the server. Precision and
rounding mode come from the `Currency` record. Monetary values cross the API as
JSON strings. `to_decimal` raises `TypeError` if handed a float.

**Why.** OMR has three decimal places and most currencies have two, so precision
is data, not a constant. A JavaScript client parsing `945.000` as a number gets
an IEEE-754 double; sending a string means the interface displays exactly what
the server computed. Raising on float turns a silent precision loss into an
immediate failure.

**Cost.** The interface must not run monetary strings through `parseFloat`. The
`DecimalString` type alias marks every such field so this is visible at the call
site.

**Open.** The default rounding mode is half-up, and the mode is a per-currency
field so it can be matched to specification section 6 without a schema change.
**This is an assumption until section 6 is available.**

---

## ADR-007 — Optimistic concurrency with an explicit version column

**Decision.** Every business record carries `version`, starting at 1 and
incremented on each update. Updates read the row with `select_for_update()`,
compare the submitted version, and return **409** on a mismatch.

**Why.** Two people editing the same quotation is normal, not exceptional.
Last-write-wins loses somebody's work silently. Pessimistic locking across a
think-time gap would hold a database lock while someone is at lunch.

**Cost.** Every update endpoint must accept and check a version, and the
interface must carry it through the form. `test_an_update_without_a_version_is_refused`
makes forgetting it a test failure rather than a silent regression.

---

## ADR-008 — Durable database outbox instead of a broker

**Decision.** Asynchronous work is rows in `core_outbox_message`, claimed by a
worker with `SELECT … FOR UPDATE SKIP LOCKED`.

**Why.** The message is written in the same transaction as the business change,
so the two can never disagree about whether something happened — which a
separate broker cannot guarantee without a distributed transaction. It also
means one fewer service for the client to operate, back up and monitor.

**Cost.** Polling latency of a couple of seconds, and load on the same database.
Both are acceptable at this product's volumes, and `SKIP LOCKED` means adding
workers needs no coordination.

**Consequence.** Delivery is at-least-once. Handlers must be idempotent, which
is what `idempotency_key` is for.

---

## ADR-009 — UUID primary keys, and identifiers are not treated as secrets

**Decision.** UUID primary keys throughout. Knowing an identifier grants
nothing.

**Why.** Sequential integers leak volume — a competitor can read your quotation
count off a URL. But unguessable identifiers are defence in depth only. Every
read and write is authorised explicitly, and the security tests call endpoints
directly with valid identifiers and no permission to prove it.

**Cost.** Slightly larger indexes. Irrelevant at this scale.

---

## ADR-010 — Company ownership modelled even though Release 1 is single-company

**Decision.** Every business record carries a `company` foreign key.
`Company.objects.default()` resolves the single active company and **raises**
rather than guessing if there are none or several.

**Why.** Retrofitting an ownership column onto a populated production database
is a migration nobody wants to write. Modelling it now costs one column.
Refusing to guess between two companies is the point: silently picking one would
write a record against the wrong legal owner.

**Cost.** Every query must scope by company. `CompanyOwnedQuerySet.for_company`
makes that one call, and forgetting it is visible in review.

---

## ADR-011 — Private storage with no URL at all

**Decision.** `MEDIA_URL` is `None`. Attachments live under
`PRIVATE_STORAGE_ROOT/<CLIENT_CODE>/`. `PrivateStorage.url()` raises
`NotImplementedError`.

**Why.** The usual mistake is an attachment directory that is also served
statically, and nobody notices until a customer's purchase order is indexed by a
search engine. Making `url()` raise means any code path that tries to publish a
file fails immediately and loudly, in development, rather than quietly working.

**Cost.** Downloads must go through a permission-checked view, which is what is
wanted anyway.

---

## ADR-012 — The test suite requires PostgreSQL

**Decision.** No SQLite fallback.

**Why.** The behaviour most worth testing — `SELECT … FOR UPDATE`, `SKIP
LOCKED`, `NUMERIC` arithmetic, deferrable constraints — either does not exist on
SQLite or behaves differently. A green suite on SQLite would be a false
assurance about the deployed system.

**Cost.** Developers need PostgreSQL. `docker compose up db` provides it.

---

## ADR-013 — React with a small hand-built component set, not a UI framework

**Decision.** React 19 + TypeScript with an original component set and stylesheet.

**Why.** The brief requires original styling and no third-party branding. A
component library would bring its own visual identity, its own upgrade cadence
and a large dependency surface, for screens that are lists and forms. Six shared
components cover the whole application.

**Cost.** Accessibility is implemented rather than inherited — labels, focus
order, `aria-describedby`, `role="alert"`. It is done, and the browser tests
locate elements by role and label, so a regression that breaks the accessible
name breaks the build.

---

## ADR-014 — The required-field marker sits outside the `<label>`

**Decision.** The asterisk is a sibling of the label text, not inside it.

**Why.** Inside the label it becomes part of the control's accessible name
("Password*"), which reads badly to a screen reader and makes the field hard to
address in tests. The input's own `required` attribute carries the meaning; the
asterisk is decoration. This was found by a browser test that could not match the
field — the component was fixed rather than the test.

---

## ADR-015 — Static files compressed but not hashed by Django

**Decision.** `CompressedStaticFilesStorage`, not the manifest variant.

**Why.** The interface's own assets are already content-hashed by the build. The
manifest storage would additionally make `collectstatic` fail the whole release
over one unreferenced asset inside a third-party package — a brittle failure
mode for no benefit here.

**Cost.** Django-served static files (the schema viewer) are cached by URL
rather than by content hash. They change once per release, so this is immaterial.

---

## ADR-016 — Order value is never labelled revenue

**Decision (recorded now, enforced in increment F).** A confirmed sales order is
a commercial commitment. No screen, report, export or event in this product may
label order value as recognised revenue, receivables or cash received, or imply
that goods were delivered, an invoice exists, or payment arrived.

**Why.** Those are accounting facts this product does not have and cannot infer.
Implying them would put wrong numbers in front of a client's finance team.

**Where it bites.** Increment F report definitions and any dashboard figure. It
is recorded here so that it is a decision with a reason rather than a style note
in a review comment.
