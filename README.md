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

```bash
git clone https://github.com/Cabir181/Ztech-ERP.git
cd Ztech-ERP && git checkout claude/new-session-8h1nxp

./scripts/quickstart.sh
```

That is the whole thing. The script checks what is installed, creates the
database and role, writes a `.env` with a freshly generated secret key,
installs both dependency sets from their lockfiles, applies migrations, builds
the interface, seeds the demo company and creates an administrator.

It is safe to run again — every step checks whether it is already done and
skips it. It never drops a database and never overwrites an existing `.env`.

Then:

```bash
./scripts/dev.sh serve          # http://127.0.0.1:8000
./scripts/dev.sh worker         # in a second terminal, for background jobs
```

Sign in at <http://127.0.0.1:8000> as `admin@example.com` with the password you
chose. You will be asked to change it on first sign-in.

### Prerequisites

The script checks for these and tells you how to install whatever is missing.

| | macOS | Debian / Ubuntu | Windows |
|---|---|---|---|
| Python 3.12 | `brew install python@3.12` | `sudo apt install python3.12 python3.12-venv` | Use WSL2, or the [Docker route](#with-docker) |
| Node 22 | `brew install node@22` | [nodejs.org packages](https://nodejs.org/en/download/package-manager) | |
| PostgreSQL 16 | `brew install postgresql@16 && brew services start postgresql@16` | `sudo apt install postgresql-16` | |
| uv | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | |

On **Windows**, run the script from WSL2 or use Docker — it is a bash script and
expects a Unix shell.

### If you would rather do it by hand

<details>
<summary>The same steps, one at a time</summary>

```bash
# 1. Database and role. The application is never given rights to create these.
sudo -u postgres psql -c "CREATE ROLE ztech LOGIN PASSWORD 'ztech' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE ztech_sales OWNER ztech;"

# 2. Configure. Set POSTGRES_* to match, and generate a secret key with
#    python -c "import secrets; print(secrets.token_urlsafe(64))"
cp .env.example .env

# 3. Install, migrate, seed
./scripts/dev.sh setup
./scripts/dev.sh migrate
ZTECH_ADMIN_PASSWORD='Choose-A-Str0ng-Passw0rd!' ./scripts/dev.sh bootstrap

# 4. Build the interface. Django serves it from frontend/dist, so without this
#    "/" returns a plain message saying the interface has not been built.
(cd frontend && npm run build)

./scripts/dev.sh serve
```

</details>

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
