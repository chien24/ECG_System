# ════════════════════════════════════════════════════════════════
#  ECG System — Production Dockerfile (single container, Render)
#  Base: python:3.10-slim (Debian Bookworm)
#  ASGI server: Daphne  |  Static files: WhiteNoise
# ════════════════════════════════════════════════════════════════
FROM python:3.10-slim

# ── Build-time metadata ───────────────────────────────────────
LABEL maintainer="ecg-system" \
      description="Real-time ECG Analysis System (production)"

# ── Environment variables ─────────────────────────────────────
# PYTHONDONTWRITEBYTECODE : do not create .pyc files in image
# PYTHONUNBUFFERED        : stdout/stderr are flushed immediately (visible in Render logs)
# PIP_NO_CACHE_DIR        : do not store pip download cache in the image layer
# PIP_DISABLE_PIP_VERSION_CHECK : suppress the version-check noise
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# ── Working directory ─────────────────────────────────────────
WORKDIR /app

# ── System dependencies ───────────────────────────────────────
# libgomp1    → required by PyTorch / scikit-learn (OpenMP threading)
# libpq-dev   → required by psycopg2 for PostgreSQL support
# gcc         → required to compile some Python C extensions
# Clean up apt cache in the same layer to keep the image slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libgomp1 \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────
# Copy requirements first to leverage Docker layer cache:
# if requirements.txt hasn't changed, pip install is skipped on rebuild
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application source code ───────────────────────────────────
# .dockerignore already excludes: .git, __pycache__, *.pyc,
# db.sqlite3, .env, venv/, staticfiles/, uploads/
COPY . .

# ── Non-root user (security best practice) ───────────────────
# Running as root inside the container is a security risk.
# Render also recommends non-root containers.
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    # staticfiles/ bị exclude trong .dockerignore nên không tồn tại trong image.
    # Tạo sẵn thư mục ở đây để Docker "seed" quyền appuser vào anonymous volume
    # khi docker-compose mount - /app/staticfiles lần đầu tiên.
    # Nếu không làm bước này, volume sẽ được tạo rỗng và owned by root
    # → appuser không ghi được → PermissionError khi collectstatic chạy.
    mkdir -p /app/staticfiles && \
    chown -R appuser:appgroup /app

USER appuser

# ── Expose port ───────────────────────────────────────────────
# Render injects $PORT at runtime; EXPOSE is documentation only
EXPOSE ${PORT}

# ── Startup script ────────────────────────────────────────────
# start.sh handles: collectstatic → migrate → daphne
CMD ["sh", "/app/start.sh"]
