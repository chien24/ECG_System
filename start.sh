#!/bin/sh
# ════════════════════════════════════════════════════════════════
#  ECG System — Container startup script
#  Runs on every container start (Render Web Service).
#  Order: collectstatic → migrate → daphne
# ════════════════════════════════════════════════════════════════
set -e   # Exit immediately if any command fails

echo "========================================"
echo "  ECG System — Starting up"
echo "  PORT: ${PORT:-8000}"
echo "========================================"

# 1. Collect static files into STATIC_ROOT (served by WhiteNoise)
echo "[1/3] Running collectstatic..."
python manage.py collectstatic --noinput --clear

# 2. Apply database migrations (safe to run on every boot)
echo "[2/3] Running migrations..."
python manage.py migrate --noinput

# 3. Start Daphne ASGI server
#    -b 0.0.0.0  → bind all interfaces (required by Render)
#    -p $PORT    → Render assigns a dynamic port via $PORT env var
echo "[3/3] Starting Daphne on 0.0.0.0:${PORT:-8000} ..."
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" ecg_system.asgi:application
