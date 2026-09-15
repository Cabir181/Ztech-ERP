# Ztech Sales

An independent, commercially licensable quote-to-order **Sales** application.

Original standalone software. It has no dependency on, and contains no code,
assets or branding from, any ERP product. Familiar sales concepts are
implemented from first principles against the product specification.

| | |
|---|---|
| **Release** | 1.0.0 |
| **Backend** | Python 3.12, Django 5.2 LTS, Django REST Framework, PostgreSQL 16 |
| **Frontend** | React 19 + TypeScript, built with Vite, served same-origin |
| **Deployment** | One deployment, one database and one private storage scope per client |

---

## Status of this build

**Increment A (foundation) is complete and tested. Increments B to F are not
started.** See [`docs/progress.md`](docs/progress.md) for exactly what exists,
what does not, and what is blocked.

One thing is worth stating up front: `Sales_Module_Specification.md` **was not
present in this workspace**. The specification is the implementation baseline
for FR01-FR23, AT01-AT32, the section 6 pricing arithmetic, the approval rules
and the report definitions. Increment A was built from the technical baseline in
the brief, which is complete and unambiguous on its own. Increments B to F
cannot be built correctly without the specification —
[`docs/progress.md`](docs/progress.md) explains why in detail.

A confirmed sales order in this product means a commercial commitment and
nothing more. It does not mean goods were delivered, an accounting invoice
exists, or payment was received. No screen, report or status in this codebase
implies otherwise.

---

## Running it locally

The quickest route is [Docker](#with-docker), which brings its own PostgreSQL.
To run it directly you need Python 3.12, Node 22, PostgreSQL 16 and
[uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Cabir181/Ztech-ERP.git && cd Ztech-ERP

# 1. Create the database and its role. The application never creates these
#    itself - it is not given rights to.
sudo -u postgres psql -c "CREATE ROLE ztech LOGIN PASSWORD 'ztech' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE ztech_sales OWNER ztech;"

# 2. Configure. Set POSTGRES_* to match step 1 and generate a secret key:
#    python -c "import secrets; print(secrets.token_urlsafe(64))"
cp .env.example .env

# 3. Install, migrate, seed
./scripts/dev.sh setup          # virtualenv, locked dependencies, npm install
./scripts/dev.sh migrate        # apply migrations to PostgreSQL
ZTECH_ADMIN_PASSWORD='Choose-A-Str0ng-Passw0rd!' ./scripts/dev.sh bootstrap

# 4. Build the interface, then run
(cd frontend && npm run build)
./scripts/dev.sh serve          # API + interface on http://127.0.0.1:8000
./scripts/dev.sh worker         # in a second terminal: the outbox worker
```

Then open <http://127.0.0.1:8000> and sign in as `admin@example.com` with the
password you set in step 3. You will be asked to change it.

`bootstrap` reads the administrator password from `ZTECH_ADMIN_PASSWORD`, or
prompts for it. It is never taken as a command line argument, because arguments
end up in shell history and in process listings.

> Step 4's `npm run build` matters: Django serves the compiled interface from
> `frontend/dist`. Without it, `/` returns a plain-text message saying the
> interface has not been built, rather than failing obscurely.

For frontend work, run `./scripts/dev.sh ui` instead and open
<http://127.0.0.1:5173>. The Vite dev server proxies `/api` to Django, so the
browser still sees one origin and the session and CSRF cookies behave exactly as
they do in production.

### With Docker

Brings its own PostgreSQL and a test mail inbox, so there is nothing to install
first beyond Docker itself.

```bash
docker compose up --build
docker compose run --rm web migrate
docker compose run --rm -e ZTECH_ADMIN_PASSWORD='<password>' web shell \
    python manage.py bootstrap_client --code demo --legal-name "Demo Trading LLC" --currency OMR
docker compose run --rm -e ZTECH_ADMIN_PASSWORD='<password>' web shell \
    python manage.py create_admin --email admin@example.com --full-name "Administrator"
```

The application is then on <http://localhost:8000> and the test email inbox on
<http://localhost:8025>. Nothing in the development stack can reach a real
recipient.

---

## Repository layout

```
backend/
  config/            Django project: settings (base/dev/test/prod), URLs, WSGI/ASGI
  ztech_sales/
    core/            Identity, companies, roles and permissions, audit, outbox, numbering
    customers/       (increment B)
    catalog/         (increment B)
    pricing/         (increment B)
    sales/           (increments C and D)
    approvals/       (increment D)
    communications/  (increment E)
    reports/         (increment F)
    integrations/    (increment F)
frontend/            React + TypeScript interface
deploy/              Dockerfile and container entrypoint
docs/                Specification mapping, decisions, deployment and operations
tests/browser/       Playwright end-to-end tests against the running application
scripts/dev.sh       Developer tasks
```

---

## Checks

```bash
./scripts/dev.sh check     # ruff, OpenAPI schema generation, and the test suite
```

The test suite runs against a real PostgreSQL database. It is not configured to
fall back to SQLite, because the behaviour that matters most here — row locking,
`SKIP LOCKED` claiming and `NUMERIC` arithmetic — does not exist on SQLite, so a
green run there would prove nothing about the deployed system.

See [`docs/testing.md`](docs/testing.md) for the browser tests and the recorded
results.

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/progress.md`](docs/progress.md) | What is built, what is not, and what is blocked |
| [`docs/implementation-checklist.md`](docs/implementation-checklist.md) | Requirement-to-code-to-test mapping |
| [`docs/architecture-decisions.md`](docs/architecture-decisions.md) | The decisions taken and why |
| [`docs/testing.md`](docs/testing.md) | How to run each suite and the recorded results |
| [`docs/deployment.md`](docs/deployment.md) | Render and portable Docker deployment |
| [`docs/client-onboarding.md`](docs/client-onboarding.md) | Standing up a new client environment |
| [`docs/backup-restore.md`](docs/backup-restore.md) | Backup, restore, upgrade and rollback |
| [`docs/user-guide.md`](docs/user-guide.md) | Guide for the people who use the application |
| [`docs/api/openapi.yaml`](docs/api/openapi.yaml) | Generated OpenAPI 3 schema |
| [`docs/api/examples.md`](docs/api/examples.md) | Request and response examples captured from a running instance |

---

## Licence

Proprietary. All rights reserved.
