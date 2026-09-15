#!/usr/bin/env bash
#
# One-command local setup for Ztech Sales.
#
#   ./scripts/quickstart.sh
#
# Checks what is installed, creates the database if it is missing, writes a .env
# with a generated secret key, installs dependencies, applies migrations, seeds
# the demo company and creates an administrator.
#
# Safe to run again: every step checks whether it is already done and skips it.
# Nothing here is destructive - it never drops a database or overwrites a .env.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

DB_NAME="${POSTGRES_DB:-ztech_sales}"
DB_USER="${POSTGRES_USER:-ztech}"
DB_PASSWORD="${POSTGRES_PASSWORD:-ztech_local_dev}"
DB_HOST="${POSTGRES_HOST:-127.0.0.1}"
DB_PORT="${POSTGRES_PORT:-5432}"

ADMIN_EMAIL="${ZTECH_ADMIN_EMAIL:-admin@example.com}"
ADMIN_NAME="${ZTECH_ADMIN_NAME:-Local Administrator}"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'

step()  { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RESET"; }
ok()    { printf '    %s%s%s\n' "$GREEN" "$1" "$RESET"; }
skip()  { printf '    %s(already done) %s%s\n' "$YELLOW" "$1" "$RESET"; }
fail()  { printf '\n%sCannot continue: %s%s\n\n' "$RED" "$1" "$RESET" >&2; exit 1; }

case "$(uname -s)" in
    Darwin) PLATFORM=macos ;;
    Linux)  PLATFORM=linux ;;
    *)      PLATFORM=other ;;
esac

install_hint() {
    case "$PLATFORM:$1" in
        macos:python)   echo "brew install python@3.12" ;;
        macos:node)     echo "brew install node@22" ;;
        macos:uv)       echo "brew install uv   (or: curl -LsSf https://astral.sh/uv/install.sh | sh)" ;;
        macos:psql)     echo "brew install postgresql@16 && brew services start postgresql@16" ;;
        linux:python)   echo "sudo apt install python3.12 python3.12-venv   (or your distribution's package)" ;;
        linux:node)     echo "see https://nodejs.org/en/download/package-manager" ;;
        linux:uv)       echo "curl -LsSf https://astral.sh/uv/install.sh | sh" ;;
        linux:psql)     echo "sudo apt install postgresql-16 && sudo systemctl start postgresql" ;;
        *:python)       echo "https://www.python.org/downloads/" ;;
        *:node)         echo "https://nodejs.org/" ;;
        *:uv)           echo "https://docs.astral.sh/uv/getting-started/installation/" ;;
        *:psql)         echo "https://www.postgresql.org/download/" ;;
    esac
}

# ---------------------------------------------------------------------------
step "Checking prerequisites"
# ---------------------------------------------------------------------------
MISSING=0
need() {
    local binary="$1" label="$2" key="$3"
    if command -v "$binary" >/dev/null 2>&1; then
        ok "$label: $(command -v "$binary")"
    else
        printf '    %smissing: %s%s\n      install with: %s\n' \
            "$RED" "$label" "$RESET" "$(install_hint "$key")" >&2
        MISSING=1
    fi
}

if command -v python3.12 >/dev/null 2>&1; then
    ok "Python 3.12: $(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
    ok "Python 3.12: $(command -v python3)"
else
    printf '    %smissing: Python 3.12%s\n      install with: %s\n' \
        "$RED" "$RESET" "$(install_hint python)" >&2
    printf '      (uv can also fetch it: uv python install 3.12)\n' >&2
    MISSING=1
fi

need node "Node.js" node
need npm  "npm"     node
need uv   "uv"      uv
need psql "psql"    psql

[ "$MISSING" -eq 0 ] || fail "install the tools listed above, then run this script again."

# ---------------------------------------------------------------------------
step "Checking PostgreSQL is running"
# ---------------------------------------------------------------------------
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
    case "$PLATFORM" in
        macos) START="brew services start postgresql@16" ;;
        linux) START="sudo systemctl start postgresql   (or: sudo pg_ctlcluster 16 main start)" ;;
        *)     START="start your PostgreSQL service" ;;
    esac
    fail "PostgreSQL is not accepting connections on $DB_HOST:$DB_PORT.
    Start it with: $START"
fi
ok "PostgreSQL is accepting connections on $DB_HOST:$DB_PORT"

# ---------------------------------------------------------------------------
step "Creating the database and role"
# ---------------------------------------------------------------------------
# The application is never given rights to create its own database, so this is
# done here with an administrative connection.
app_can_connect() {
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        -d "$DB_NAME" -tAc 'SELECT 1' >/dev/null 2>&1
}

admin_psql() {
    # Try the current user first (usual on macOS/Homebrew), then the postgres
    # superuser (usual on Linux packages).
    if psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -d postgres -tAc 'SELECT 1' >/dev/null 2>&1; then
        psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -d postgres -c "$1"
    elif psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -tAc 'SELECT 1' >/dev/null 2>&1; then
        psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -c "$1"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -u postgres psql -c "$1"
    elif [ "$(id -u)" -eq 0 ]; then
        su postgres -c "psql -c \"$1\""
    else
        return 1
    fi
}

if app_can_connect; then
    skip "$DB_USER can already reach $DB_NAME"
else
    if ! admin_psql "SELECT 1" >/dev/null 2>&1; then
        fail "no administrative PostgreSQL connection is available, so the database
    cannot be created automatically. Create it yourself and run this again:

      sudo -u postgres psql -c \"CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD' CREATEDB;\"
      sudo -u postgres psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER;\""
    fi
    admin_psql "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD' CREATEDB;" >/dev/null 2>&1 \
        && ok "created role $DB_USER" || skip "role $DB_USER exists"
    admin_psql "CREATE DATABASE $DB_NAME OWNER $DB_USER;" >/dev/null 2>&1 \
        && ok "created database $DB_NAME" || skip "database $DB_NAME exists"

    app_can_connect || fail "created the database but $DB_USER still cannot connect to it.
    Check your pg_hba.conf allows password authentication from $DB_HOST."
    ok "$DB_USER can reach $DB_NAME"
fi

# ---------------------------------------------------------------------------
step "Writing .env"
# ---------------------------------------------------------------------------
# An existing .env is never overwritten - it may hold real settings.
if [ -f "$ROOT/.env" ]; then
    skip ".env exists and was left untouched"
else
    SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
    cat > "$ROOT/.env" <<ENVFILE
# Generated by scripts/quickstart.sh for LOCAL DEVELOPMENT ONLY.
# Never deploy with these values; see .env.example for what each one means.
CLIENT_CODE=local
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=$SECRET
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173

POSTGRES_DB=$DB_NAME
POSTGRES_USER=$DB_USER
POSTGRES_PASSWORD=$DB_PASSWORD
POSTGRES_HOST=$DB_HOST
POSTGRES_PORT=$DB_PORT

PRIVATE_STORAGE_ROOT=$ROOT/var/private
ATTACHMENT_SCANNER=stub

# Email is intentionally unset. The application reports it as "not configured"
# and refuses to queue customer messages, rather than pretending to send them.
EMAIL_HOST=
DEFAULT_FROM_EMAIL=
ENVFILE
    chmod 600 "$ROOT/.env"
    ok "wrote .env with a freshly generated secret key"
fi

# ---------------------------------------------------------------------------
step "Installing dependencies"
# ---------------------------------------------------------------------------
( cd "$BACKEND" && uv sync --extra dev --quiet )
ok "backend dependencies installed from uv.lock"

( cd "$FRONTEND" && npm install --no-audit --no-fund --silent )
ok "frontend dependencies installed from package-lock.json"

PY="$BACKEND/.venv/bin/python"

# ---------------------------------------------------------------------------
step "Applying database migrations"
# ---------------------------------------------------------------------------
( cd "$BACKEND" && "$PY" manage.py migrate --noinput )
ok "database schema is up to date"

# ---------------------------------------------------------------------------
step "Building the interface"
# ---------------------------------------------------------------------------
# Django serves the compiled interface from frontend/dist, so this has to happen
# before the site will render anything.
( cd "$FRONTEND" && npm run build --silent )
ok "interface built into frontend/dist"

# ---------------------------------------------------------------------------
step "Seeding the demo company"
# ---------------------------------------------------------------------------
( cd "$BACKEND" && "$PY" manage.py bootstrap_client \
    --code demo --legal-name "Demo Trading LLC" --trade-name "Demo Trading" \
    --currency OMR --timezone Asia/Muscat --verbosity 0 )
ok "company, five built-in roles and document sequences are in place"

# ---------------------------------------------------------------------------
step "Creating the administrator"
# ---------------------------------------------------------------------------
ADMIN_EXISTS=$( cd "$BACKEND" && "$PY" -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from ztech_sales.core.models import User
print('yes' if User.objects.filter(email='$ADMIN_EMAIL').exists() else 'no')
" )

if [ "$ADMIN_EXISTS" = "yes" ]; then
    skip "$ADMIN_EMAIL already exists - its password was left alone"
else
    if [ -z "${ZTECH_ADMIN_PASSWORD:-}" ]; then
        printf '    Choose a password for %s (at least 12 characters).\n' "$ADMIN_EMAIL"
        printf '    It is read from the prompt, never from a command argument.\n\n'
    fi
    ( cd "$BACKEND" && "$PY" manage.py create_admin \
        --email "$ADMIN_EMAIL" --full-name "$ADMIN_NAME" --allow-existing )
fi

# ---------------------------------------------------------------------------
printf '\n%s%s Setup complete.%s\n\n' "$BOLD" "$GREEN" "$RESET"
cat <<NEXT
  Start the application:

      ./scripts/dev.sh serve        # http://127.0.0.1:8000
      ./scripts/dev.sh worker       # in a second terminal, for background jobs

  Then sign in at http://127.0.0.1:8000 as ${ADMIN_EMAIL}.
  You will be asked to change the password on first sign-in.

  Other useful commands:

      ./scripts/dev.sh ui           # Vite dev server on :5173, for frontend work
      ./scripts/dev.sh test         # the backend test suite
      ./scripts/dev.sh check        # lint, schema and tests together

  Note: outbound email is deliberately not configured. The application will say
  so plainly rather than reporting messages as sent.
NEXT
