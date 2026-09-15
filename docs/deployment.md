# Deployment

Covers a portable Docker deployment and Render. The same tagged image serves
every client; nothing is baked in per client.

---

## 1. What a deployment consists of

| Component | Purpose | Notes |
|---|---|---|
| **web** | Gunicorn serving the API and the compiled interface, same origin | Stateless apart from sessions in the database |
| **worker** | The durable outbox worker | At least one. More is fine — claiming uses `SKIP LOCKED` |
| **database** | PostgreSQL 16 | Holds business data, sessions and the outbox |
| **private files** | Persistent volume for attachments | Must **not** be inside any published directory |
| **email** | SMTP provider | Optional. Without it the application says "not configured" and refuses to queue customer messages |
| **scanning** | Attachment scan service | **Required in production.** The stub is refused by `config/settings/prod.py` |

Migrations run once per release from the `migrate` role, not from the web
process. Running them from every replica races them against each other.

---

## 2. Environment variables

Start from [`.env.example`](../.env.example), which lists every variable with an
explanation. The ones production will not start without:

| Variable | Why it is required |
|---|---|
| `DJANGO_SECRET_KEY` | Signs sessions and CSRF tokens. Generate per environment: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DJANGO_ALLOWED_HOSTS` | Host header allow-list |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | The https origins the browser uses |
| `POSTGRES_*` | Database connection |
| `CLIENT_CODE` | Namespaces private storage and log lines. One per client |
| `PRIVATE_STORAGE_ROOT` | Where attachments live |
| `ATTACHMENT_SCANNER` | Must not be `stub`; the process refuses to start if it is |

Secrets come from the platform's secret store, never from a file in the image
and never from the repository.

---

## 3. Portable Docker deployment

Works on any Docker host, and is the reference the other targets follow.

```bash
# Build the release image once. It contains the API and the compiled interface.
docker build -f deploy/Dockerfile -t ztech-sales:1.0.0 .

# Apply migrations (once per release, before rolling the web processes)
docker run --rm --env-file /etc/ztech/acme.env ztech-sales:1.0.0 migrate

# Web
docker run -d --name ztech-acme-web \
  --env-file /etc/ztech/acme.env \
  -v /srv/ztech/acme/private:/var/lib/ztech-sales/private \
  -p 127.0.0.1:8001:8000 \
  --restart unless-stopped \
  ztech-sales:1.0.0 web

# Worker
docker run -d --name ztech-acme-worker \
  --env-file /etc/ztech/acme.env \
  -v /srv/ztech/acme/private:/var/lib/ztech-sales/private \
  --restart unless-stopped \
  ztech-sales:1.0.0 worker
```

Put a TLS-terminating reverse proxy in front, forwarding `X-Forwarded-Proto`
(which `SECURE_PROXY_SSL_HEADER` reads) and `X-Forwarded-For`.

The image runs as an unprivileged user, collects static files at build time so
the container needs no write access to them, and exposes a health check on
`/api/system/health/`.

> **Not yet verified.** `docker build` and `docker compose build` were not run in
> the environment where this release was prepared. The Dockerfile is written and
> reviewed but the build itself is **NOT RUN** — run it before the first client
> deployment.

### Two clients on one host

Each client gets its own env file, its own database, its own private directory
and its own port. The image is identical.

```
/etc/ztech/acme.env    CLIENT_CODE=acme    POSTGRES_DB=ztech_acme    port 8001
/etc/ztech/globex.env  CLIENT_CODE=globex  POSTGRES_DB=ztech_globex  port 8002
```

See [`client-onboarding.md`](client-onboarding.md) for the full procedure.

---

## 4. Render

Render fits this shape well: a web service, a background worker, a managed
PostgreSQL instance and a persistent disk.

### Services

| Render service | Type | Command |
|---|---|---|
| `ztech-<client>-web` | Web Service (Docker) | `web` |
| `ztech-<client>-worker` | Background Worker (Docker) | `worker` |
| `ztech-<client>-db` | PostgreSQL 16 | — |

Both services build from `deploy/Dockerfile` with the repository root as the
build context.

### Settings

- **Health check path:** `/api/system/health/`
- **Disk:** mount a persistent disk at `/var/lib/ztech-sales/private` on **both**
  the web and worker services. The worker renders documents into the same
  private scope the web process serves them from.
- **Pre-deploy command:** `migrate` — this is Render's mechanism for running
  migrations exactly once per deploy rather than once per replica.
- **Environment:** copy from `.env.example`. Set `DJANGO_SETTINGS_MODULE=config.settings.prod`.
  `DJANGO_CSRF_TRUSTED_ORIGINS` must be the https origin Render serves, for
  example `https://ztech-acme.onrender.com` or the client's own domain.

Render terminates TLS at the edge and forwards the original scheme in
`X-Forwarded-Proto`, which production settings already read.

### First deploy

```bash
# From the Render shell on the web service, once:
python manage.py bootstrap_client \
    --code acme --legal-name "Acme Trading LLC" \
    --trade-name "Acme" --currency OMR --timezone Asia/Muscat

ZTECH_ADMIN_PASSWORD='<generated>' python manage.py create_admin \
    --email admin@acme.example --full-name "Acme Administrator"
```

Then clear `ZTECH_ADMIN_PASSWORD` from the environment. The account is flagged
to change its password at first sign-in.

> This repository does **not** deploy anything automatically and creates no paid
> infrastructure. The steps above are run deliberately by a person with the
> authority to do so.

---

## 5. Release procedure

1. Tag the release. The same tag deploys to every client.
2. Back up the database (see [`backup-restore.md`](backup-restore.md)). Do this
   before migrating, every time.
3. Run `migrate` once.
4. Roll the web processes.
5. Roll the worker processes.
6. Check `/api/system/health/`, then sign in and check
   `/api/system/status/` — it reports email and scanning as configured or not,
   honestly.
7. Run `manage.py check_roles` and act on anything it reports.

Rolling web before worker is deliberate: the outbox is durable, so messages
queued by the new web processes simply wait until the new workers are up.

---

## 6. Operational checks

| Check | How |
|---|---|
| Liveness | `GET /api/system/health/` — public, and deliberately reveals nothing |
| Readiness detail | `GET /api/system/status/` — requires `settings.view` |
| Outbox backlog | `SELECT status, count(*) FROM core_outbox_message GROUP BY status;` |
| Stuck messages | Any row in `dead` needs a person. `last_error` says why |
| Request tracing | Every response carries `X-Request-ID`; the same id is on the audit entry |
| Failed sign-ins | `SELECT email, failed_login_count, locked_until FROM core_user WHERE failed_login_count > 0;` |

### Alert on

- `core_outbox_message` rows in `dead` — delivery has genuinely failed.
- Outbox rows in `pending` older than a few minutes — the worker is not running.
- `/api/system/health/` returning 503 — the database is unreachable.
- A rising rate of 409 responses — two people are fighting over the same records,
  which is usually a process problem rather than a software one.
