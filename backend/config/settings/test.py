"""Settings used by the automated test suite.

Tests run against a real PostgreSQL database because the application relies on
PostgreSQL behaviour that SQLite does not reproduce: ``SELECT ... FOR UPDATE``
row locking, ``NUMERIC`` arithmetic and deferrable unique constraints.
"""

from __future__ import annotations

from config.settings.base import *  # noqa: F403
from config.settings.base import DATABASES, PRIVATE_STORAGE_ROOT

DEBUG = False
SECRET_KEY = "test-only-secret-key-not-used-outside-the-test-suite"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only; tests never ship

DATABASES["default"]["ATOMIC_REQUESTS"] = False

MEDIA_ROOT = PRIVATE_STORAGE_ROOT / "test"

ATTACHMENT_SCANNER = "stub"

LOGGING["root"]["level"] = "ERROR"  # noqa: F405
LOGGING["loggers"]["ztech_sales"]["level"] = "ERROR"  # noqa: F405
