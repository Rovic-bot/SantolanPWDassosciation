#!/usr/bin/env bash
set -euo pipefail

if [[ "${DJANGO_SETTINGS_MODULE:-}" != "config.settings_production" ]]; then
  echo "Set DJANGO_SETTINGS_MODULE=config.settings_production before building." >&2
  exit 1
fi
python -m pip install -r requirements-production.txt
# Fail the build if the native MySQL extension cannot load on this Linux image.
python -c "import MySQLdb; import gunicorn; import storages; import boto3"
python manage.py check --deploy
python manage.py collectstatic --noinput
# Never migrate or seed data during a build. The release operator separately
# reviews/applies migrations to the approved deployment database after backup.
