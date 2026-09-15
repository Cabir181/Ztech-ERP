"""Local development settings. Never use this module for a client deployment."""

from __future__ import annotations

from config.env import env_list
from config.settings.base import *  # noqa: F403
from config.settings.base import ALLOWED_HOSTS

DEBUG = True
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", [*ALLOWED_HOSTS, "0.0.0.0", "web", "testserver"])

# The Vite dev server proxies /api to this process, so the browser origin stays
# the same and the session/CSRF cookie pair keeps working unchanged.
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
)
