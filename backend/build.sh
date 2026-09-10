#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python -m pip install -r requirements.lock.txt
python manage.py collectstatic --noinput
# Apply the committed schema to the same DATABASE_URL used by the web service.
# Stop deployment if a migration fails; do not serve against missing tables.
python manage.py migrate --noinput
python manage.py migrate --check
# Creates the first administrator only when all DJANGO_SUPERUSER_* variables are set.
python manage.py bootstrap_admin
