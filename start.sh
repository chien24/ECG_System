#!/bin/sh
# ════════════════════════════════════════════════════════════════
#  ECG System — Container startup script
#  Runs on every container start (Render Web Service).
#  Order: collectstatic → migrate → createsuperuser → daphne
#
#  WHY auto-create superuser?
#    Render free tier does NOT provide shell access to running containers.
#    There is no way to run "python manage.py createsuperuser" manually
#    after deployment. We must automate it here, using env vars for creds.
# ════════════════════════════════════════════════════════════════
set -e   # Exit immediately if any command fails

echo "========================================"
echo "  ECG System — Starting up"
echo "  PORT: ${PORT:-8000}"
echo "========================================"

# 1. Collect static files into STATIC_ROOT (served by WhiteNoise)
echo "[1/4] Running collectstatic..."
python manage.py collectstatic --noinput --clear

# 2. Apply database migrations (safe to run on every boot)
echo "[2/4] Running migrations..."
python manage.py migrate --noinput

# 3. Create Django superuser automatically.
#
#    Render free tier has no shell access → we cannot run createsuperuser
#    interactively after deploy. So we automate it here every startup.
#
#    Required environment variables (set in Render Dashboard → Environment):
#      DJANGO_SUPERUSER_USERNAME  – e.g. "admin"
#      DJANGO_SUPERUSER_EMAIL     – e.g. "admin@example.com"
#      DJANGO_SUPERUSER_PASSWORD  – a strong password
#
#    Idempotency: if the superuser already exists, Django exits with code 1.
#    The "|| true" turns that into success so the container keeps running.
#    This makes the step completely safe to run on every container restart.
echo "[3/4] Creating superuser (skipped silently if already exists)..."
python manage.py createsuperuser --noinput || true

# 4. Start Daphne ASGI server
#    -b 0.0.0.0  → bind all interfaces (required by Render)
#    -p $PORT    → Render assigns a dynamic port via $PORT env var
echo "[4/4] Starting Daphne on 0.0.0.0:${PORT:-8000} ..."
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" ecg_system.asgi:application
