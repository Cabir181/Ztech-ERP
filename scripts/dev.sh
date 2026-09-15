#!/usr/bin/env bash
# Developer conveniences. Run from the repository root: ./scripts/dev.sh <task>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/bin/python"

usage() {
    cat <<'USAGE'
Tasks:
  setup      create the virtualenv, install locked dependencies, install npm packages
  migrate    apply database migrations
  bootstrap  create the demo company, roles and sequences, then an administrator
  serve      run the API on http://127.0.0.1:8000
  worker     run the outbox worker
  ui         run the Vite dev server on http://127.0.0.1:5173
  test       run the backend test suite against PostgreSQL
  lint       run ruff check and ruff format --check
  schema     regenerate docs/api/openapi.yaml
  check      lint, schema and tests - what CI runs
USAGE
}

case "${1:-}" in
    setup)
        cd "$BACKEND" && uv sync --extra dev
        cd "$ROOT/frontend" && npm install
        ;;
    migrate)   cd "$BACKEND" && "$PY" manage.py migrate ;;
    bootstrap)
        cd "$BACKEND"
        "$PY" manage.py bootstrap_client --code demo --legal-name "Demo Trading LLC" \
            --trade-name "Demo Trading" --currency OMR --timezone Asia/Muscat
        "$PY" manage.py create_admin --email admin@example.com --full-name "Local Administrator" --allow-existing
        ;;
    serve)     cd "$BACKEND" && "$PY" manage.py runserver 127.0.0.1:8000 ;;
    worker)    cd "$BACKEND" && "$PY" manage.py run_worker ;;
    ui)        cd "$ROOT/frontend" && npm run dev ;;
    test)      cd "$BACKEND" && "$PY" -m pytest "${@:2}" ;;
    lint)      cd "$BACKEND" && .venv/bin/ruff check . && .venv/bin/ruff format --check . ;;
    schema)    cd "$BACKEND" && "$PY" manage.py spectacular --file "$ROOT/docs/api/openapi.yaml" --fail-on-warn ;;
    check)
        "$0" lint
        "$0" schema
        "$0" test
        ;;
    *) usage; exit 1 ;;
esac
