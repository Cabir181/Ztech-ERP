"""Shared Django settings for the Ztech Sales application.

Environment-specific modules (``dev``, ``prod``, ``test``) import everything from
here and override only what differs. Secrets are never hard-coded: every value
that varies per deployment is read from the process environment.
"""

from __future__ import annotations

from pathlib import Path

from config.env import env_bool, env_int, env_list, env_str, load_dotenv

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = BASE_DIR.parent

load_dotenv(REPO_DIR / ".env")

# ---------------------------------------------------------------------------
# Client / deployment identity
# ---------------------------------------------------------------------------
# One deployment, one database and one isolated attachment storage scope per
# client. CLIENT_CODE names the tenant that this process serves and is used to
# namespace attachment storage, document sequences and operational logging.
CLIENT_CODE = env_str("CLIENT_CODE", "local")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env_str("DJANGO_SECRET_KEY", "insecure-development-key-do-not-use-in-production")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "ztech_sales.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ztech_sales.core.middleware.RequestContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", "ztech_sales"),
        "USER": env_str("POSTGRES_USER", "ztech"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", "ztech"),
        "HOST": env_str("POSTGRES_HOST", "127.0.0.1"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        "ATOMIC_REQUESTS": False,
        "OPTIONS": {},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "core.User"

AUTHENTICATION_BACKENDS = ["ztech_sales.core.auth_backends.EmailBackend"]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": env_int("PASSWORD_MIN_LENGTH", 12)},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Failed-login throttling (FR: account protection).
LOGIN_MAX_FAILED_ATTEMPTS = env_int("LOGIN_MAX_FAILED_ATTEMPTS", 10)
LOGIN_LOCKOUT_SECONDS = env_int("LOGIN_LOCKOUT_SECONDS", 900)

# ---------------------------------------------------------------------------
# Sessions, CSRF and transport security
# ---------------------------------------------------------------------------
# The SPA is served same-origin with the API, so cookie-based session
# authentication with CSRF protection is used rather than bearer tokens.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "ztech_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 12 * 60 * 60)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_NAME = "ztech_csrftoken"
CSRF_COOKIE_HTTPONLY = False  # the SPA must read it to echo it in the X-CSRFToken header
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])
CSRF_FAILURE_VIEW = "ztech_sales.core.views.csrf_failure"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
# Timestamps are stored in UTC. Business rules that are date-sensitive (for
# example quotation expiry) are evaluated in the owning company's timezone,
# which is a per-company field rather than a process-wide setting.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Compressed but not hashed: the interface's own assets are already
    # content-hashed by the build, and a manifest would make collectstatic fail
    # the whole release over one unreferenced asset in a third-party package.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# The compiled single-page interface is served from this same process, so the
# browser talks to one origin for both the pages and the API. That is what lets
# session cookies and CSRF protection work without any cross-origin exceptions.
FRONTEND_DIST = Path(env_str("FRONTEND_DIST", str(REPO_DIR / "frontend" / "dist")))
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.is_dir() else None
WHITENOISE_INDEX_FILE = False
# Hashed build assets may be cached hard; index.html must not be.
WHITENOISE_MAX_AGE = env_int("WHITENOISE_MAX_AGE", 60 * 60 * 24 * 365)

# Attachments are PRIVATE. They are stored outside the web root and are only
# ever delivered through a permission-checked download view; there is no static
# URL that maps onto this directory.
PRIVATE_STORAGE_ROOT = Path(env_str("PRIVATE_STORAGE_ROOT", str(REPO_DIR / "var" / "private")))
MEDIA_ROOT = PRIVATE_STORAGE_ROOT / CLIENT_CODE
MEDIA_URL = None

MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "ztech_sales.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "ztech_sales.core.exceptions.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": True,
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Ztech Sales API",
    "DESCRIPTION": "Quote-to-order Sales application - Release 1.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api",
}

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# There is no silent fallback to a console backend: if SMTP is not configured
# the application reports an honest "not configured" status instead of
# pretending that messages were sent.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env_str("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 30)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "")

# ---------------------------------------------------------------------------
# Attachment scanning
# ---------------------------------------------------------------------------
# "stub" is a development-only adapter and refuses to start when DEBUG is off.
ATTACHMENT_SCANNER = env_str("ATTACHMENT_SCANNER", "stub")
ATTACHMENT_SCANNER_URL = env_str("ATTACHMENT_SCANNER_URL", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] [client=" + CLIENT_CODE + "] %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "ztech_sales": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
