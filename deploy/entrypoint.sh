#!/bin/sh
# Container entrypoint. The first argument selects the process role.
#
#   web      gunicorn serving the API and the compiled interface
#   worker   the durable outbox worker
#   migrate  apply migrations and exit (run once per release, before web)
#   shell    an interactive shell for support work
set -eu

ROLE="${1:-web}"

wait_for_database() {
    echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432} ..."
    attempt=0
    until python -c "
import os, sys
import psycopg
try:
    psycopg.connect(
        dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'], host=os.environ['POSTGRES_HOST'],
        port=os.environ.get('POSTGRES_PORT', '5432'), connect_timeout=3,
    ).close()
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 60 ]; then
            echo "PostgreSQL did not become reachable in time." >&2
            exit 1
        fi
        sleep 2
    done
    echo "PostgreSQL is reachable."
}

case "$ROLE" in
    web)
        wait_for_database
        # Migrations are NOT run here. Running them from every web replica races
        # them against each other; run the `migrate` role once per release.
        exec gunicorn config.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers "${GUNICORN_WORKERS:-3}" \
            --threads "${GUNICORN_THREADS:-4}" \
            --timeout "${GUNICORN_TIMEOUT:-60}" \
            --graceful-timeout 30 \
            --access-logfile - \
            --error-logfile - \
            --forwarded-allow-ips '*'
        ;;
    worker)
        wait_for_database
        exec python manage.py run_worker --batch-size "${WORKER_BATCH_SIZE:-10}"
        ;;
    migrate)
        wait_for_database
        python manage.py migrate --noinput
        echo "Migrations applied."
        ;;
    shell)
        shift
        exec "$@"
        ;;
    *)
        echo "Unknown role '$ROLE'. Expected one of: web, worker, migrate, shell." >&2
        exit 64
        ;;
esac
