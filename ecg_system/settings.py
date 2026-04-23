"""
Django settings for ecg_system project.

Production-ready configuration for deployment on Render.
All secrets and environment-specific values are read from
environment variables — never hardcoded.

Environment variables required in production:
  SECRET_KEY            – Django secret key
  DATABASE_URL          – PostgreSQL connection string
                          e.g. postgresql://user:pass@host:5432/dbname
  DJANGO_ALLOWED_HOSTS  – Space-separated list of allowed hosts
                          e.g. "ecg-system.onrender.com"
  USE_REDIS             – "1" to use Redis channel layer (optional, default 0)
  REDIS_URL             – Redis connection URL if USE_REDIS=1
                          e.g. redis://red-xxxxx:6379
  PORT                  – Injected automatically by Render (default 8000)
"""

from pathlib import Path
import os
import dj_database_url  # type: ignore

# ── Base directory ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════
#  SECURITY
# ══════════════════════════════════════════════════════════════

# SECURITY WARNING: must be a long, random string in production.
# Set via the SECRET_KEY environment variable on Render.
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    # Fallback only for local dev — NEVER rely on this in production
    'django-insecure-change-me-in-production-env-var'
)

# SECURITY WARNING: must be False in production.
# Default True for local development to avoid production-only static pipeline issues.
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

# Allowed hosts: Render automatically assigns a *.onrender.com domain.
# Set DJANGO_ALLOWED_HOSTS to your Render URL (space-separated for multiple).
# Example: "ecg-system.onrender.com myapp.example.com"
_raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost 127.0.0.1')
ALLOWED_HOSTS = _raw_hosts.split()

# Trust Render's reverse proxy headers so HTTPS is detected correctly
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── CSRF trusted origins (needed for POST requests over HTTPS) ─
# Automatically add https:// prefix to all ALLOWED_HOSTS entries
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}"
    for host in ALLOWED_HOSTS
    if not host.startswith(('localhost', '127.0.0.1'))
]


# ══════════════════════════════════════════════════════════════
#  APPLICATION DEFINITION
# ══════════════════════════════════════════════════════════════

INSTALLED_APPS = [
    'daphne',                                   # Must be first (replaces runserver)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'users',
    'ecg',
]

ASGI_APPLICATION = 'ecg_system.asgi.application'


# ══════════════════════════════════════════════════════════════
#  CHANNELS LAYER
# ══════════════════════════════════════════════════════════════

USE_REDIS = os.environ.get('USE_REDIS', '0') == '1'
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')

if USE_REDIS:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [REDIS_URL],
            },
        },
    }
else:
    # InMemoryChannelLayer — suitable for single-instance deployments (Render free tier)
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }


# ══════════════════════════════════════════════════════════════
#  AUTH REDIRECTS
# ══════════════════════════════════════════════════════════════

LOGIN_REDIRECT_URL = 'ecg:home'
LOGOUT_REDIRECT_URL = 'users:login'
LOGIN_URL = 'users:login'


# ══════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ══════════════════════════════════════════════════════════════

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise must come right after SecurityMiddleware to serve
    # compressed, cached static files without a separate CDN.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ecg_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecg_system.wsgi.application'


# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════
# Production: PostgreSQL via DATABASE_URL (provided by Render Postgres add-on).
# Local dev fallback: SQLite (only if DATABASE_URL is not set).
#
# DATABASE_URL format:
#   postgresql://USER:PASSWORD@HOST:PORT/DBNAME

_database_url = os.environ.get('DATABASE_URL')

if _database_url:
    DATABASES = {
        'default': dj_database_url.parse(
            _database_url,
            conn_max_age=600,       # Keep connections open for 10 minutes
            conn_health_checks=True,
        )
    }
else:
    # Fallback for local development without a DATABASE_URL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ══════════════════════════════════════════════════════════════
#  PASSWORD VALIDATION
# ══════════════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ══════════════════════════════════════════════════════════════
#  INTERNATIONALIZATION
# ══════════════════════════════════════════════════════════════

LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True


# ══════════════════════════════════════════════════════════════
#  STATIC FILES
# ══════════════════════════════════════════════════════════════
# WhiteNoise serves compressed + versioned static files directly
# from the Django process — no separate nginx/CDN needed on Render.

STATIC_URL = '/static/'

# collectstatic copies all static files here; WhiteNoise serves from here.
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Use simple storage in DEBUG, manifest storage in production.
if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    # WhiteNoise: compress & add content-hash fingerprints for long-lived caching
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    # Prevent 500 when manifest is temporarily stale after static refactors.
    # WhiteNoise will serve the unhashed path until collectstatic is re-run.
    WHITENOISE_MANIFEST_STRICT = False


# ══════════════════════════════════════════════════════════════
#  MISC
# ══════════════════════════════════════════════════════════════

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model (matches ERD)
AUTH_USER_MODEL = 'users.User'
