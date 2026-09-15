"""Environment variable access helpers.

All deployment-specific configuration is supplied through the process
environment. Nothing secret is ever committed to the repository; see
``.env.example`` at the repository root for the full list of variables.
"""

from __future__ import annotations

import os
from pathlib import Path

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ImproperlyConfigured(Exception):
    """Raised when a required environment variable is missing or unusable."""


def load_dotenv(path: Path) -> None:
    """Populate ``os.environ`` from a ``KEY=value`` file, if it exists.

    Existing environment variables always win, so a real deployment can never be
    overridden by a stray file on disk. Intended for local development only.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_str(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        if required:
            raise ImproperlyConfigured(f"Required environment variable {name} is not set.")
        return ""
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    normalised = raw.strip().lower()
    if normalised in _TRUE:
        return True
    if normalised in _FALSE:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean, got {raw!r}.")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Environment variable {name} must be an integer, got {raw!r}.") from exc


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]
