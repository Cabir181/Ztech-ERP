"""Private, per-client attachment storage.

Files are never served from a static URL. They live under
``PRIVATE_STORAGE_ROOT/<CLIENT_CODE>/`` - outside anything the web server maps -
and are only ever delivered by a view that has already checked the caller's
permission on the record the file belongs to.

Each client deployment sets its own ``CLIENT_CODE``, so two clients sharing a
host still write into separate directory trees.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
MAX_FILENAME_LENGTH = 120


class UnsafePath(ValueError):
    """Raised when a caller-supplied path would escape the client's storage scope."""


def client_storage_root() -> Path:
    """The single directory tree this deployment may write attachments into."""
    root = Path(settings.MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    return root.resolve()


def _fold(part: str) -> str:
    """Fold one filename component to safe ASCII."""
    folded = unicodedata.normalize("NFKD", part).encode("ascii", "ignore").decode("ascii")
    return _UNSAFE.sub("_", folded).strip("._")


def sanitise_filename(filename: str) -> str:
    """Reduce an uploaded filename to something safe to put on disk.

    The original name is kept in the database for display; only the stored name
    is rewritten. Directory separators, traversal segments, control characters
    and non-ASCII forms are all removed rather than escaped.

    The stem and the extension are folded separately, so a name written in a
    non-Latin script - which is ordinary here - keeps its extension instead of
    having the whole name collapse into it.
    """
    raw = (filename or "").replace("\\", "/").split("/")[-1].strip()
    stem, dot, suffix = raw.rpartition(".")
    if not dot:
        stem, suffix = raw, ""

    stem = _fold(stem) or "file"
    suffix = _fold(suffix)[:16]
    if not suffix:
        return stem[:MAX_FILENAME_LENGTH]
    return f"{stem[: MAX_FILENAME_LENGTH - len(suffix) - 1]}.{suffix}"


def resolve_private_path(*parts: str) -> Path:
    """Resolve a path inside the client's storage scope, or refuse.

    Anything that resolves outside the root - ``..`` segments, an absolute path,
    a symlink pointing away - raises :class:`UnsafePath` instead of being
    clamped, so a caller cannot half-succeed at escaping.
    """
    root = client_storage_root()
    candidate = root.joinpath(*[str(part) for part in parts])
    resolved = Path(candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise UnsafePath(f"{'/'.join(str(p) for p in parts)!r} resolves outside the client storage scope.")
    return resolved


class PrivateStorage(FileSystemStorage):
    """File storage with no public URL.

    ``url()`` raises rather than returning something: if any code path ever
    tries to hand a browser a direct link to an attachment, it fails loudly at
    that point instead of quietly publishing the file.
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("location", str(settings.MEDIA_ROOT))
        kwargs.setdefault("base_url", None)
        kwargs.setdefault("file_permissions_mode", 0o640)
        kwargs.setdefault("directory_permissions_mode", 0o750)
        super().__init__(**kwargs)

    def url(self, name: str) -> str:
        raise NotImplementedError(
            "Attachments have no public URL. Serve them through the permission-checked download view instead."
        )


private_storage = PrivateStorage
