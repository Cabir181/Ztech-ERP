# API examples

Every example below was captured from a running instance, not written by hand.
The full machine-readable contract is in [`openapi.yaml`](openapi.yaml), also
browsable at `/api/schema/docs/` on a running deployment.

---

## Conventions

| | |
|---|---|
| **Base path** | `/api/` on the same origin as the interface |
| **Authentication** | Session cookie (`ztech_sessionid`), set by `POST /api/auth/login/` |
| **CSRF** | Every mutating request sends the `ztech_csrftoken` cookie value in the `X-CSRFToken` header |
| **Money** | JSON **strings**, at the currency's precision. Never parse them as numbers |
| **Concurrency** | Reads return `version`; updates send back the version they read |
| **Tracing** | Every response carries `X-Request-ID`, which also appears on the audit entry |

### The error envelope

Every error, without exception, has this shape:

```json
{
  "error": {
    "code": "stale_object",
    "message": "Human-readable, safe to show an internal user.",
    "details": { "field": ["Per-field messages, when there are any."] }
  }
}
```

Switch on `code`, not on `message`.

---

## Signing in

The CSRF cookie has to exist before the first mutating request, and it is
**rotated on sign-in** — read it again from the cookie jar afterwards rather
than reusing the one you sent.

```bash
BASE=https://sales.acme.example

# 1. Obtain the CSRF cookie
curl -s -c jar.txt "$BASE/api/auth/csrf/"
TOKEN=$(grep ztech_csrftoken jar.txt | awk '{print $7}')

# 2. Sign in
curl -s -b jar.txt -c jar.txt -X POST "$BASE/api/auth/login/" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $TOKEN" \
  -H "Referer: $BASE/" \
  -d '{"email":"admin@acme.example","password":"..."}'

# 3. The token has changed - re-read it before the next mutation
TOKEN=$(grep ztech_csrftoken jar.txt | awk '{print $7}')
```

**200 OK**

```json
{
  "user": {
    "id": "9c57d2e3-b36e-4318-b2f8-d06168fcdc4c",
    "email": "admin@acme.example",
    "full_name": "Local Administrator",
    "job_title": "",
    "phone": "",
    "is_active": true,
    "is_system_administrator": true,
    "must_change_password": true,
    "is_locked": false,
    "last_login": "2026-09-15T14:34:26.170993Z",
    "date_joined": "2026-09-15T13:53:38.282919Z",
    "roles": [
      { "id": "1db1684b-5538-46ec-a9f8-56d5fd63ffdb", "code": "system_administrator", "name": "System Administrator" }
    ],
    "version": 69
  },
  "company": {
    "id": "d1837fb4-8776-4c15-b7de-f8d2b4dbee52",
    "code": "acme",
    "display_name": "Acme Trading",
    "legal_name": "Acme Trading LLC",
    "timezone": "Asia/Muscat",
    "currency_code": "OMR",
    "currency_symbol": "OMR",
    "decimal_places": 3,
    "brand_primary_color": "#1F3A5F",
    "brand_accent_color": "#2F7D6E"
  },
  "permissions": ["activity.manage", "approval.request", "..."],
  "must_change_password": true
}
```

`decimal_places: 3` is the Omani rial. Render and submit monetary values at that
precision.

### Sign-in refused

**401 Unauthorized** — identical for a wrong password and an unknown account, on
purpose:

```json
{ "error": { "code": "invalid_credentials", "message": "Email address or password is not correct." } }
```

**403 Forbidden** — only reachable by someone who supplied the right password:

```json
{
  "error": {
    "code": "account_locked",
    "message": "Too many failed sign-in attempts. Try again later.",
    "details": { "locked_until": "2026-09-15T15:12:44.019Z" }
  }
}
```

---

## Reading the session

```http
GET /api/auth/session/
```

Same payload as sign-in. The interface calls this on first paint to decide what
to show. It is the authoritative list of what the signed-in user may do — but
the server re-checks on every request regardless.

---

## Listing users

```http
GET /api/users/?search=rae&is_active=true&page=1&page_size=25
```

**200 OK**

```json
{
  "count": 1,
  "page": 1,
  "page_size": 25,
  "total_pages": 1,
  "results": [
    {
      "id": "8e0f...",
      "email": "rae@acme.example",
      "full_name": "Rae Representative",
      "job_title": "Sales Executive",
      "is_active": true,
      "is_system_administrator": false,
      "must_change_password": false,
      "is_locked": false,
      "last_login": "2026-09-15T09:02:11.331Z",
      "date_joined": "2026-09-01T06:00:00Z",
      "roles": [{ "id": "b2c1...", "code": "sales_representative", "name": "Sales Representative" }],
      "version": 3
    }
  ]
}
```

Query parameters: `search` (name or email), `is_active` (`true`/`false`),
`role` (role code), `page`, `page_size` (capped at 200 by the server).

---

## Creating a user

```http
POST /api/users/
X-CSRFToken: <token>
Content-Type: application/json

{
  "email": "new.person@acme.example",
  "full_name": "New Person",
  "job_title": "Sales Executive",
  "initial_password": "An-Initial-Str0ng-Passw0rd!",
  "role_ids": ["b2c1..."]
}
```

**201 Created** returns the user. `must_change_password` is `true` whenever an
initial password was set. `role_ids` **replaces** the whole set of assignments,
which is what makes the resulting audit entry a complete statement of what the
user may now do.

---

## Updating, and the concurrency contract

Send back the `version` you read. This is not optional.

```http
PATCH /api/users/8e0f.../
Content-Type: application/json

{ "job_title": "Senior Sales Executive", "version": 3 }
```

**409 Conflict** — somebody else saved first. **Nothing was written.**

```json
{
  "error": {
    "code": "stale_object",
    "message": "This record was changed by someone else since you opened it. Reload the record and reapply your changes.",
    "details": { "current_version": 14, "submitted_version": 1 }
  }
}
```

Reload, show the user what changed, and let them reapply. Do not retry
automatically with the new version — that is exactly the silent overwrite the
409 exists to prevent.

**422 Unprocessable Entity** — version omitted entirely:

```json
{
  "error": {
    "code": "business_rule_violated",
    "message": "A version must be supplied when updating an existing record.",
    "details": { "version": ["This field is required when updating an existing record."] }
  }
}
```

---

## Validation failures

**400 Bad Request**, with per-field messages ready to render next to the inputs:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "The submitted data is not valid.",
    "details": {
      "email": ["Enter a valid email address."],
      "initial_password": [
        "This password is too short. It must contain at least 12 characters.",
        "This password is too common."
      ]
    }
  }
}
```

---

## Permission failures

**403 Forbidden**, naming the permission that would have been enough:

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have permission to perform this action.",
    "details": { "required_any_of": ["user.view"] }
  }
}
```

Not signed in at all:

```json
{ "error": { "code": "not_authenticated", "message": "Authentication credentials were not provided." } }
```

A record the caller may not see reports **404**, not 403, so the API never
confirms that an identifier exists:

```json
{ "error": { "code": "not_found", "message": "The requested record does not exist." } }
```

---

## Roles and the permission catalogue

```http
GET /api/system/permissions/
```

```json
[
  {
    "code": "quotation.override_price",
    "module": "sales",
    "label": "Override unit prices",
    "description": "Enter a unit price other than the pricelist price."
  }
]
```

```http
PATCH /api/roles/<id>/
{ "permissions": ["customer.view", "quotation.create", "quotation.view.own"], "version": 2 }
```

`permissions` replaces the role's whole set. An unrecognised code is rejected
with `validation_failed` rather than being stored and ignored.

---

## Audit trail

```http
GET /api/audit-events/?entity_type=core.user&entity_id=8e0f...
```

```json
{
  "count": 1,
  "page": 1,
  "page_size": 25,
  "total_pages": 1,
  "results": [
    {
      "id": "0b7a...",
      "occurred_at": "2026-09-15T10:31:02.884Z",
      "actor_label": "Ada Administrator <admin@acme.example>",
      "action": "user.updated",
      "entity_type": "core.user",
      "entity_id": "8e0f...",
      "entity_label": "Rae Representative",
      "summary": "Updated user rae@acme.example.",
      "changes": { "job_title": { "from": "Sales Executive", "to": "Senior Sales Executive" } },
      "request_id": "421203cc-dfb1-4d43-af46-55b853889600",
      "ip_address": "10.0.0.14",
      "source": "web"
    }
  ]
}
```

Read only. There is no route that modifies or deletes an audit entry.

---

## Health and status

```http
GET /api/system/health/     # public; reveals nothing
```

```json
{ "status": "ok", "time": "2026-09-15T14:13:08.695494+00:00" }
```

```http
GET /api/system/status/     # requires settings.view
```

```json
{
  "client_code": "acme",
  "release": "1.0.0",
  "debug": false,
  "database": { "engine": "postgresql", "connected": true },
  "email": {
    "status": "not_configured",
    "host": null,
    "from_address": null,
    "detail": "EMAIL_HOST and DEFAULT_FROM_EMAIL are not set; email cannot be sent and will not be reported as sent."
  },
  "attachment_scanning": {
    "adapter": "stub",
    "status": "development_stub",
    "detail": "The stub adapter accepts uploads without scanning and is refused in production settings."
  },
  "private_storage_root": "/var/lib/ztech-sales/private/acme"
}
```

`not_configured` is a real, supported state. The application says so rather than
falling back to something that accepts a message and drops it.
