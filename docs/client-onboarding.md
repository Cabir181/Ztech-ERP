# Client onboarding

Standing up a new client environment. One deployment, one database and one
private storage scope per client, from the same tagged codebase.

There are no per-client source forks. Everything that differs between clients is
an environment variable or a database record.

---

## 1. Before you start

| Needed | Why |
|---|---|
| Registered legal name | Appears on customer documents |
| Trading name | Shown in the interface and on documents when it differs |
| Short client code | Namespaces storage and log lines. Lower case, no spaces: `acme` |
| Currency | Drives monetary precision. **OMR has three decimal places** |
| Time zone | IANA name, for example `Asia/Muscat`. Date-sensitive rules are evaluated here |
| Named administrator | A real person with a real email address. Never a shared account |
| Hostname | The https origin the client will use |

Currency and time zone are asked for up front because they change the meaning of
stored data. Changing precision after amounts exist restates history, so
`bootstrap_client` warns rather than silently changing it.

---

## 2. Provision

```bash
CLIENT=acme

createdb  ztech_${CLIENT}
createuser ztech_${CLIENT} --pwprompt

mkdir -p /srv/ztech/${CLIENT}/private
chown 1001:1001 /srv/ztech/${CLIENT}/private
chmod 750       /srv/ztech/${CLIENT}/private
```

The private directory must not be inside anything the web server publishes. The
application never generates a URL into it — see
[`architecture-decisions.md`](architecture-decisions.md) ADR-011.

---

## 3. Configure

Copy `.env.example` to `/etc/ztech/${CLIENT}.env` and set at least:

```ini
CLIENT_CODE=acme
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<unique per client; never shared>
DJANGO_ALLOWED_HOSTS=sales.acme.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://sales.acme.example
POSTGRES_DB=ztech_acme
POSTGRES_USER=ztech_acme
POSTGRES_PASSWORD=<unique per client>
PRIVATE_STORAGE_ROOT=/srv/ztech/acme/private
ATTACHMENT_SCANNER=icap
ATTACHMENT_SCANNER_URL=<scan service>
```

Every client gets its **own** secret key and database password. Reusing a key
across clients means one client's session cookie is valid at another's.

---

## 4. Initialise

```bash
docker run --rm --env-file /etc/ztech/acme.env ztech-sales:1.0.0 migrate

docker run --rm --env-file /etc/ztech/acme.env ztech-sales:1.0.0 shell \
    python manage.py bootstrap_client \
      --code acme --legal-name "Acme Trading LLC" \
      --trade-name "Acme" --currency OMR --timezone Asia/Muscat

docker run --rm --env-file /etc/ztech/acme.env \
    -e ZTECH_ADMIN_PASSWORD='<generated>' ztech-sales:1.0.0 shell \
    python manage.py create_admin \
      --email admin@acme.example --full-name "Acme Administrator"
```

`bootstrap_client` is idempotent — it is safe to run again on every release, and
it will refresh the built-in roles if a release adds a permission.

`create_admin` takes the password from the environment or prompts. It is never a
command line argument, because arguments end up in shell history and in `ps`
output. Clear the variable afterwards. The account is flagged to change its
password at first sign-in.

---

## 5. Verify the environment is genuinely isolated

Do this for every client, not just the first.

```bash
# 1. Health
curl -fsS https://sales.acme.example/api/system/health/

# 2. Sign in as the administrator and confirm the status screen reports
#    the right client code, the right private storage path, and email and
#    scanning as they actually are.

# 3. Confirm the private directory is not reachable over http.
curl -I https://sales.acme.example/private/
curl -I https://sales.acme.example/var/lib/ztech-sales/private/
#    Both must fail. Neither path is served by anything.

# 4. Confirm this client's credentials do not work on another client.
#    Sign in to acme with a globex account: it must be refused.
```

Step 4 is the one people skip. It is the one that matters: distinct databases
mean the account does not exist, and distinct secret keys mean a session cookie
from one environment is not valid in another.

---

## 6. Hand over to the client

1. Sign in as the administrator and change the password.
2. Complete **Company** settings: legal name, tax and commercial registration
   numbers, address, contact details, brand colours and the document footer.
   > The document footer is printed on customer documents. Internal notes and
   > approval policy must never go there.
3. Create named user accounts. One per person; never a shared login, because
   every approval and acceptance record names a real user.
4. Assign roles. Start from the built-in five and adjust:
   - **Approver** must be assigned deliberately. Approval authority is *not*
     granted by the administrator flag, so an environment with no Approver has
     nobody who can decide an approval.
   - Give **Sales Representative** to people who should only see their own
     quotations, **Sales Manager** to people who should see everyone's.
5. Walk the client's administrator through the audit trail. It is their evidence
   of who did what, and it cannot be edited or deleted by anyone.
6. Confirm the backup schedule is running and that a restore has been rehearsed
   — see [`backup-restore.md`](backup-restore.md).

---

## 7. What to tell the client about this release

Be direct about it:

- A confirmed sales order is a **commercial commitment**. It does not mean goods
  were delivered, an invoice exists, or payment arrived. No screen in the product
  says otherwise.
- Release 1 currently delivers identity, roles, company configuration and the
  audit trail. The sales workflow arrives in the increments that follow — see
  [`progress.md`](progress.md).
- Email is not configured until they give you SMTP details. Until then the
  application says so plainly and refuses to queue customer messages. It will
  never report a message as sent when nothing was delivered.
