# Testing

How to run each suite, and the results actually observed on 15 September 2026.

Nothing in this document is a claim about a command that was not run. Where a
test could not be executed in this environment it is marked **NOT RUN** and the
exact command is given so it can be run where it can be.

---

## 1. Backend suite

```bash
./scripts/dev.sh test
# or:  cd backend && .venv/bin/python -m pytest
```

Runs against a real PostgreSQL 16 database. There is no SQLite fallback — see
[`architecture-decisions.md`](architecture-decisions.md) ADR-012.

### Observed result

```
154 passed in 8.98s
```

| Module | Tests | Covers |
|---|---:|---|
| `test_auth_api.py` | 19 | Sign-in, CSRF on sign-in, enumeration resistance, lockout, session rotation, revocation on an open session, password change, honest email status |
| `test_security.py` | 22 | Anonymous access to every protected endpoint, CSRF on every mutation, cookie flags, direct API calls without permission, 404 vs 403, protected fields, audit immutability, secret redaction, last-administrator guard, no stack traces |
| `test_client_isolation.py` | 18 | Per-client storage namespacing, no public URL, path traversal, hostile and non-Latin filenames |
| `test_users_api.py` | 17 | User CRUD, permissions, 409 on stale writes, self-lockout guards, role replacement, query-count ceiling |
| `test_base_models.py` | 15 | Version lifecycle, actor stamping, partial saves, company scoping, sequence period reset, email normalisation |
| `test_money.py` | 13 | Float rejection, currency precision, OMR three places, half-up and half-even, working precision |
| `test_company.py` | 12 | Company time zone vs UTC, ISO 4217 precision, unambiguous company resolution, change sets, audit actor retention |
| `test_outbox.py` | 11 | Enqueue, idempotency keys, scheduling, backoff, dead state, error truncation, unknown topics, worker behaviour |
| `test_permissions_model.py` | 11 | Role resolution, built-in role integrity, administrator/approval separation, retired codes, company scoping |
| `test_roles_api.py` | 11 | Role CRUD, permission catalogue, built-in role protection, 409, company settings |
| `test_concurrency.py` | 5 | Two real threads racing an edit, ten threads allocating numbers, rollback releasing a number, two workers claiming |

`test_concurrency.py` uses real threads and real connections, not mocks. The
outcomes it asserts (`["saved", "stale"]`, ten distinct references, disjoint
claim sets) are only achievable if the locking is genuinely correct.

---

## 2. Lint, formatting and schema

```bash
./scripts/dev.sh lint      # ruff check + ruff format --check
./scripts/dev.sh schema    # regenerate docs/api/openapi.yaml with --fail-on-warn
./scripts/dev.sh check     # all of the above plus the test suite
```

### Observed result

```
All checks passed!
59 files already formatted
OpenAPI schema written to docs/api/openapi.yaml   (0 warnings, 0 errors)
154 passed
```

`--fail-on-warn` means an endpoint whose request or response shape cannot be
derived fails the build rather than being silently omitted from the schema.

---

## 3. Frontend build and type check

```bash
cd frontend && npm run build     # tsc --noEmit && vite build
```

### Observed result

```
tsc --noEmit: no errors (strict, noUncheckedIndexedAccess, noUnusedLocals)
vite build:   43 modules transformed
  dist/index.html                0.65 kB
  dist/assets/index-*.css       11.43 kB │ gzip: 2.97 kB
  dist/assets/index-*.js       299.86 kB │ gzip: 92.91 kB
```

---

## 4. Browser tests

End-to-end against the real application: a real Django process, a real
PostgreSQL database and the compiled interface served same-origin. Nothing is
stubbed.

```bash
# 1. build the interface and start the stack
cd frontend && npm run build
cd ../backend && .venv/bin/python manage.py runserver 127.0.0.1:8009 --noreload

# 2. in another terminal
cd tests/browser && npm install
ZTECH_BASE_URL=http://127.0.0.1:8009 \
ZTECH_ADMIN_PASSWORD='<the administrator password for that environment>' \
  npx playwright test
```

If the machine has a pre-provisioned Chromium (a CI image, for example), point
at it instead of downloading one:

```bash
PLAYWRIGHT_CHROMIUM=/opt/pw-browsers/chromium npx playwright test
```

The suite refuses to run without `ZTECH_ADMIN_PASSWORD`. No password literal is
committed, not even a development one.

```bash
```

### Observed result

```
Running 5 tests using 1 worker
  ✓ the sign-in screen refuses the wrong password without saying whether the account exists
  ✓ an administrator signs in and reaches every administration screen
  ✓ creating a user writes a real record and an audit entry
  ✓ a sales representative is not offered administration and is refused it directly
  ✓ a second editor is told their copy is stale instead of overwriting the first
  5 passed (11.6s)
```

Run twice in succession with the same result, which confirms the suite leaves no
state behind that the next run depends on.

What these prove, beyond "the page rendered":

- Creating a user through the interface writes a real PostgreSQL row **and** an
  audit entry, both verified by reloading from the server.
- A sales representative sees no administration navigation, is refused the
  screen when they type the address, **and** is refused the API when the request
  never touches the interface at all — same 403, same error code.
- Two browser sessions editing the same record produce one saved change and one
  honest conflict message, not a silent overwrite.

Screenshots of each run are in [`evidence/screenshots/`](evidence/screenshots/).

---

## 5. Performance and load — **NOT RUN**

No performance fixture was executed, and no benchmark figures appear anywhere in
this repository. Publishing invented numbers would be worse than publishing
none.

There is also nothing meaningful to load-test yet: the quotation, pricing and
reporting code paths that would be measured are in increments C to F, and the
dataset shape and concurrency targets are defined in the specification section
that is not present (see [`progress.md`](progress.md) §1).

When the specification and increments C to F exist, run the fixture and report:
observed figures, hardware (CPU model, cores, RAM), PostgreSQL version and
settings, dataset size, concurrency level, the measurement method, and the
percentiles — not an average alone.

---

## 6. Other checks — status

| Check | Status | Note |
|---|---|---|
| Direct unauthorised API calls | **Done** | `test_security.py`; also asserted from the browser suite |
| Mutation CSRF | **Done** | Every mutating endpoint, parametrised |
| Permission revocation | **Done** | Verified on an already-open session |
| Attachment request authorisation | **Partial** | Storage isolation and traversal are tested; the download endpoint arrives in increment E |
| Two independent client environments | **Partial** | Storage and configuration isolation proven by test; two live environments side by side **NOT RUN** — procedure in [`client-onboarding.md`](client-onboarding.md) |
| Backup and restore | **NOT RUN** | Procedure in [`backup-restore.md`](backup-restore.md) |
| CSV formula neutralisation | **Not started** | Increment F |
| Spoofed upload handling | **Not started** | Increment E |
| Docker image build | **NOT RUN** | `docker compose build` was not executed in this environment |
| AT01–AT32 | **BLOCKED** | Specification missing |

---

## 7. Writing new tests

- Test the behaviour a client would notice, not the implementation. `test_two_simultaneous_edits_leave_exactly_one_winner` is a better test than one that asserts a version counter incremented.
- Anything touching locking or numbering needs `@pytest.mark.django_db(transaction=True)` and real threads. A mock proves nothing about PostgreSQL.
- Security tests call the API directly. A test that only checks a hidden button proves the interface is tidy, not that the system is safe.
- Browser tests locate elements by role and label, so a change that breaks an accessible name breaks the build.
