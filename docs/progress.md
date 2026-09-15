# Progress

**Release 1.0.0 · Increment A complete · Increments B to F not started**
Last updated: 15 September 2026

---

## 1. The blocking issue, stated plainly

`Sales_Module_Specification.md` version 1.0 **is not in this workspace**, and is
not anywhere on this machine. The repository was empty apart from `.git` when
this work began. The only file supplied was the coding brief itself.

The brief is explicit that the specification, not the brief, is the
implementation baseline. The specification is the only source for:

| What is missing | What depends on it |
|---|---|
| **FR01–FR23** | Every functional behaviour in increments B to F |
| **AT01–AT32** | The acceptance tests that are the contractual definition of done |
| **Section 6 pricing arithmetic** | Line, discount, tax and total formulas; rounding order; where each rounding occurs |
| **Permission matrix** | Which role may do what, per action and per state |
| **Revision rules** | Supersession, what a new revision invalidates, numbering |
| **Approval triggers** | The concession thresholds and how they are evaluated |
| **Report definitions** | Exactly which figures each report shows and how quote families are counted |
| **Integration event contract** | Event names, payload shape, versioning |

These cannot be inferred. Getting the rounding *order* wrong in section 6, for
instance, produces totals that are out by a baisa on some lines and right on
others — which is worse than not shipping, because it is discovered by the
client's accountant rather than by a test.

### What was done about it

Increment A does not depend on the specification. The brief's **technical
baseline** section specifies it completely and unambiguously: the stack, the
module layout, the deployment and isolation model, same-origin session
authentication with CSRF, the durable database outbox, and locked dependency
versions. That is what was built, in full, with tests.

The one pricing fact the brief states directly — AT01 yields **900.000 net,
45.000 tax, 945.000 total** in OMR — is consistent with the Decimal money
foundation that is in place and tested (three decimal places, half-up rounding,
no float anywhere). The arithmetic that produces those figures belongs to
increment C and is not implemented, because the formula that produces them is in
section 6.

### What is needed to continue

Add `Sales_Module_Specification.md` to the repository root. Increments B to F
can then proceed directly from the current codebase — the module packages,
permission catalogue, audit trail, outbox, numbering and concurrency control
they build on are already in place and tested.

---

## 2. What is built and working

Everything below runs against a real PostgreSQL 16 database and is covered by
tests that were executed, not assumed. See [`testing.md`](testing.md) for the
recorded results.

### Foundation
- Python 3.12, Django 5.2.17 LTS, DRF 3.18.1, PostgreSQL 16, all pinned in
  `backend/uv.lock`. Versions were checked against the published package index
  rather than guessed.
- Module packages created for `core`, `customers`, `catalog`, `pricing`,
  `sales`, `approvals`, `communications`, `reports` and `integrations`. Only
  `core` has content in this increment.
- Split settings: `base`, `dev`, `test`, `prod`. Production refuses to start
  without `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and
  `DJANGO_CSRF_TRUSTED_ORIGINS`, and refuses to start at all with the
  development scan stub enabled.

### Identity and authorisation
- Email sign-in, Argon2 password hashing, failed-attempt lockout, session
  rotation on sign-in, timing-equalised responses so a missing account cannot be
  told apart from a wrong password.
- A permission catalogue of 39 codes declared in code, and roles stored in the
  database referencing them. Five built-in roles are seeded per client.
- **Approval authority is never conferred by the administrator flag.** It is
  granted only by a role, so "who may approve" is always answerable from the
  role assignments. This is the segregation-of-duties control that increment D's
  self-approval rule will build on.
- Every endpoint — list, detail, action and settings — checks permission on the
  server. Tests call the API directly, without the interface, to prove it.
- Deactivating an account ends access on the next request, including on a
  session that is already open.
- The environment cannot be left with nobody able to administer it.

### Data integrity
- Decimal money throughout, never float. Precision comes from the currency
  record: OMR is seeded with three decimal places, per ISO 4217. The helper
  raises rather than accepting a float.
- Optimistic concurrency on every business record. A stale write returns **409**
  with the current and submitted versions, and changes nothing. Proved with two
  real threads, not simulated.
- Gap-free document numbering allocated under a row lock inside the caller's
  transaction, so a rolled-back save releases the number. Proved with ten
  concurrent threads.
- An append-only audit trail. Entries cannot be updated or deleted through the
  ORM or through any route, and secrets are redacted before they are written.
- Company time zone held on the company record. Date-sensitive rules are
  evaluated there, not in UTC and not in the viewer's zone — which is what makes
  quotation expiry correct in Oman.

### Asynchronous work
- A durable database outbox with idempotency keys, exponential backoff, a dead
  state after retries are exhausted, and `SELECT … FOR UPDATE SKIP LOCKED`
  claiming. No broker, no Redis, no second datastore that can disagree with the
  database about whether the business change happened.
- A worker process that survives one bad message and parks an unknown topic
  immediately rather than retrying a deployment error for hours.

### Client isolation
- One deployment, one database and one private attachment directory per client,
  namespaced by `CLIENT_CODE`.
- Attachments have no public URL at all. `PrivateStorage.url()` raises, so any
  code path that ever tries to hand a browser a direct link fails loudly instead
  of quietly publishing the file.
- Path traversal is refused, not clamped. Uploaded filenames are folded to safe
  ASCII with the stem and extension handled separately, so an Arabic filename
  keeps its extension.

### Interface
- React 19 + TypeScript, served same-origin by the Django process, so session
  cookies and CSRF need no cross-origin exceptions anywhere.
- Sign-in, overview, users, roles with a permission editor, company settings,
  audit trail and password change. All of it reads and writes PostgreSQL through
  the API. Nothing is stored in `localStorage` and there is no static JSON
  anywhere.
- Navigation is filtered by permission, and screens are gated too — but both are
  usability measures. The tests prove the server refuses the request regardless.
- Keyboard operation, visible focus rings, labelled controls, per-field errors,
  loading states, empty states, unsaved-change warnings, light and dark, and a
  layout that works down to phone width.
- Branding colours come from the company record at runtime, so a client's
  colours apply without a rebuild and without a source fork.

---

## 3. What is NOT built

Stated so nobody plans around something that is not here.

| Area | State |
|---|---|
| Customers, addresses, contacts | Not started (increment B) |
| Products, units of measure, taxes | Not started (increment B) |
| Pricelists, payment terms, templates | Not started (increment B) |
| Quotations, lines, pricing arithmetic | Not started (increment C) |
| Approvals, revisions, acceptance, confirmation | Not started (increment D) |
| Customer PDFs, attachments, email delivery, activities | Not started (increment E) |
| Reporting, CSV export, integration events | Not started (increment F) |
| AT01–AT32 | Not implemented — the acceptance criteria are in the missing specification |
| Performance fixture and load test | **NOT RUN** — see [`testing.md`](testing.md) |
| Attachment scan adapter | Only the development stub exists, and production settings refuse it |
| Email delivery | Not implemented. The application reports email as "not configured" and never claims a message was sent |

Nothing in the interface pretends any of the above exists. There are no
placeholder buttons and no non-functional menu entries.

---

## 4. Next steps

1. **Add the specification.** Everything below is blocked on it.
2. Increment B: customers, catalog, taxes, terms, pricelists and templates, on
   the `CompanyOwnedModel` and permission foundation already in place.
3. Increment C: quotations and the section 6 arithmetic, using the Decimal
   helpers already tested.
4. Increment D: approvals, immutable issue snapshots, revisions, confirmation.
   The self-approval rule builds on the segregation control already in place.
5. Increment E: documents, attachments, email — on the outbox already running.
6. Increment F: reporting, exports, integration events, load test.

---

## 5. Known limitations

- **One legal company per environment.** Ownership is modelled explicitly on
  every record, so a second company is a configuration change rather than a
  schema rewrite, but the resolver deliberately refuses to guess between two
  active companies today.
- **The development scan stub does not scan anything.** It is refused by
  production settings, and the status screen says so in plain words.
- **The outbox worker is a polling loop**, not an event-driven consumer. At the
  volumes this product targets that is the right trade: no broker to operate.
  It is a single process; horizontal scaling works because claiming uses
  `SKIP LOCKED`, but that has been tested with two workers, not twenty.
- **Session storage is the database.** Simple and correct; it adds a write per
  request because `SESSION_SAVE_EVERY_REQUEST` keeps sliding expiry honest.
- **Browser tests need a running stack.** They are not self-provisioning; the
  commands are in [`testing.md`](testing.md).
