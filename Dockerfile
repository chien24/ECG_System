# ════════════════════════════════════════════════════════════════
#  ECG System — Dockerfile tối ưu
#  Base: python:3.10-slim (Debian Bookworm)
# ════════════════════════════════════════════════════════════════
FROM python:3.10-slim

# ── Biến môi trường ───────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── Thư mục làm việc ──────────────────────────────────────────
WORKDIR /app

# ── System dependencies ───────────────────────────────────────
# libgomp1  → cần cho PyTorch / scikit-learn (OpenMP)
# libpq-dev → cần nếu sau này chuyển sang PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Cài Python dependencies ───────────────────────────────────
# Copy requirements trước để tận dụng Docker layer cache:
# Nếu không thay đổi requirements.txt, bước này sẽ được cache lại
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy source code ──────────────────────────────────────────
# .dockerignore đã loại trừ: .git, __pycache__, *.ipynb,
# db.sqlite3, venv/, .env, uploads/, staticfiles/
COPY . .

# ── Tạo non-root user (security best practice) ───────────────
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

# ── Port ──────────────────────────────────────────────────────
EXPOSE 8000

# ── Chạy Daphne ASGI server ───────────────────────────────────
# Bind 0.0.0.0 để Docker port mapping hoạt động
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "ecg_system.asgi:application"]
