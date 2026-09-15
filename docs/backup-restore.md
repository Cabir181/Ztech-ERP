# Backup, restore, upgrade and rollback

A backup that has never been restored is not a backup. The rehearsal in §3 is
part of onboarding, not an optional extra.

---

## 1. What has to be backed up

| What | Where | If it is lost |
|---|---|---|
| **Database** | PostgreSQL | Everything: customers, quotations, orders, users, roles, the audit trail, sessions, the outbox |
| **Private attachments** | `PRIVATE_STORAGE_ROOT/<CLIENT_CODE>/` | Uploaded customer documents and generated PDFs. Not reproducible |
| **Environment file** | `/etc/ztech/<client>.env` | Secret key and credentials. Losing the secret key invalidates every session, which is survivable; losing the database password is not |

The database and the attachment directory must be backed up **together and
close in time**. A database row pointing at a file that is not in the backup is
a broken record, and the repair is manual.

---

## 2. Taking a backup

```bash
CLIENT=acme
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST=/srv/backups/${CLIENT}/${STAMP}
mkdir -p "${DEST}"

# Database. Custom format so pg_restore can be selective on the way back.
pg_dump --format=custom --no-owner --no-privileges \
        --file "${DEST}/database.dump" \
        "postgresql://ztech_${CLIENT}@localhost/ztech_${CLIENT}"

# Attachments.
tar --create --gzip \
    --file "${DEST}/private-files.tar.gz" \
    --directory "/srv/ztech/${CLIENT}" private

# Configuration, excluding nothing - it is all needed to rebuild.
cp "/etc/ztech/${CLIENT}.env" "${DEST}/environment.env"
chmod 600 "${DEST}/environment.env"

sha256sum "${DEST}"/* > "${DEST}/SHA256SUMS"
```

Backups contain credentials and customer data. Encrypt them at rest, restrict
access to the people who administer that client, and keep them off the
application host.

### Schedule

| Frequency | Retention | Notes |
|---|---|---|
| Nightly | 30 days | Full database and attachments |
| Weekly | 12 weeks | |
| Monthly | 12 months | Check against the client's own retention obligations |
| Before every release | Until the release is confirmed good | §4 |

---

## 3. Restoring — and rehearsing it

Restore into a **scratch environment**, never over a live one, until the moment
you have decided the live one is lost.

```bash
CLIENT=acme
SRC=/srv/backups/${CLIENT}/20260915T020000Z

sha256sum --check "${SRC}/SHA256SUMS"

createdb ztech_${CLIENT}_restore
pg_restore --no-owner --no-privileges --dbname ztech_${CLIENT}_restore \
           "${SRC}/database.dump"

mkdir -p /srv/ztech/${CLIENT}_restore
tar --extract --gzip --file "${SRC}/private-files.tar.gz" \
    --directory "/srv/ztech/${CLIENT}_restore"

# Point a throwaway environment at the restored copies and start it.
docker run --rm -p 127.0.0.1:8099:8000 \
  -e CLIENT_CODE=${CLIENT} \
  -e POSTGRES_DB=ztech_${CLIENT}_restore \
  -e PRIVATE_STORAGE_ROOT=/var/lib/ztech-sales/private \
  -v /srv/ztech/${CLIENT}_restore/private:/var/lib/ztech-sales/private \
  --env-file "${SRC}/environment.env" \
  ztech-sales:1.0.0 web
```

### Verify the restore — all of it

A restore is verified when **every** line below passes, not when the service
starts.

- [ ] `/api/system/health/` returns `ok`.
- [ ] An existing user can sign in with their existing password.
- [ ] Roles and permissions match what they were.
- [ ] The audit trail's most recent entry is from close to the backup time.
- [ ] `/api/system/status/` reports the expected client code and storage path.
- [ ] An attachment recorded in the database opens and its content is right.
      (Applies once increment E ships attachments.)
- [ ] Document sequence `next_value` is at or ahead of the highest reference in
      use — otherwise the next document reuses a number.

Then drop the scratch database and directory.

**Rehearse this quarterly, and after any change to the backup job.**

---

## 4. Upgrading

```bash
# 1. Back up. Before migrating. Every time. No exceptions.
#    (§2)

# 2. Pull the new tag
docker pull ztech-sales:1.1.0

# 3. Migrate once - not once per replica
docker run --rm --env-file /etc/ztech/acme.env ztech-sales:1.1.0 migrate

# 4. Roll web, then worker
docker stop ztech-acme-web    && docker rm ztech-acme-web    && <start web on 1.1.0>
docker stop ztech-acme-worker && docker rm ztech-acme-worker && <start worker on 1.1.0>

# 5. Refresh the built-in roles in case the release added a permission
docker run --rm --env-file /etc/ztech/acme.env ztech-sales:1.1.0 shell \
    python manage.py bootstrap_client --code acme --legal-name "Acme Trading LLC" \
      --currency OMR --timezone Asia/Muscat

# 6. Report role permissions the release has retired
docker run --rm --env-file /etc/ztech/acme.env ztech-sales:1.1.0 shell \
    python manage.py check_roles
```

Web before worker is deliberate: the outbox is durable, so anything the new web
processes queue simply waits for the new workers.

### After upgrading

- [ ] `/api/system/health/` is `ok`.
- [ ] Sign in and open the overview.
- [ ] `/api/system/status/` shows the new release number.
- [ ] The outbox has no rows stuck in `pending` — the worker is running.
- [ ] `check_roles` reports nothing, or you have acted on what it reported.

---

## 5. Rolling back

### Code only, no migration in the release

Straightforward:

```bash
docker stop ztech-acme-web ztech-acme-worker
docker rm   ztech-acme-web ztech-acme-worker
# start both on the previous tag
```

### The release contained a migration

This is the case that needs a decision, not a script.

1. **Check whether the migration is reversible.**
   `python manage.py migrate core <previous_migration_name> --plan` shows what
   would run. A migration that dropped a column cannot give the data back.

2. **If it is reversible and no data has been written that depends on it,**
   migrate backwards and then roll the code back.

3. **If it is not reversible, or business data has been written since,** restore
   the pre-upgrade backup (§3). This loses everything entered since the upgrade,
   so it is a decision for the client, not for the person holding the terminal.
   Say plainly what will be lost before doing it.

4. Either way, tell the client what happened, what was lost, and what was
   preserved. The audit trail is intact up to the restore point and is the
   record of what existed.

### The decision, in one line

If the release is minutes old and nobody has entered anything, restore. If
people have been working in it all day, do not restore without asking — fix
forward instead.

---

## 6. Disaster recovery

Rebuilding a client from nothing:

1. Provision a host, Docker and PostgreSQL 16.
2. Restore `environment.env` from the backup, or rebuild it from
   [`.env.example`](../.env.example) and the client's record.
3. Create the database and restore the dump (§3).
4. Restore the attachment directory with its ownership and `750` permissions.
5. Start web and worker on the tag that matches the backup — **not** the latest
   tag. A newer image may expect migrations the restored database has not had.
6. Work through the verification list in §3.
7. Only then point DNS at the new host.

Record the recovery time objective and recovery point objective agreed with each
client, and check the backup schedule actually meets them. A nightly backup
means a client can lose up to a day of quotations; if that is unacceptable to
them, the schedule needs changing, not the documentation.
