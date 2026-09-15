"""Production settings.

Every secret and host-specific value is required from the environment; there are
no insecure defaults. Import failures here are deliberate - the process must not
start in a half-configured state.
"""

from __future__ import annotations

from config.env import ImproperlyConfigured, env_bool, env_list, env_str
from config.settings.base import *  # noqa: F403
from config.settings.base import ATTACHMENT_SCANNER

DEBUG = False

SECRET_KEY = env_str("DJANGO_SECRET_KEY", required=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list the hostnames this deployment serves.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "DJANGO_CSRF_TRUSTED_ORIGINS must list the https origins the browser uses, "
        "for example https://sales.example.com."
    )

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Render and most managed platforms terminate TLS at the edge and forward the
# original scheme in this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# A development scan stub must never protect a production upload path.
if ATTACHMENT_SCANNER == "stub":
    raise ImproperlyConfigured(
        "ATTACHMENT_SCANNER=stub is a development-only adapter. Configure a real scan "
        "service (ATTACHMENT_SCANNER=icap or clamav with ATTACHMENT_SCANNER_URL) before "
        "accepting uploads in production."
    )
