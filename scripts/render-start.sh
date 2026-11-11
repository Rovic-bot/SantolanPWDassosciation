#!/bin/sh
set -eu
# Runtime-only secrets never enter image layers. Migrations and restores are
# deliberately separate operator actions; startup never seeds or resets data.
python manage.py check --deploy
python manage.py collectstatic --noinput --verbosity 0
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 --threads 3 --timeout 180 --graceful-timeout 180 \
    --max-requests 500 --max-requests-jitter 50 --error-logfile -
