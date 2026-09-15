"""One deployment, one database, one attachment storage scope per client."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings

from ztech_sales.core.storage import (
    PrivateStorage,
    UnsafePath,
    client_storage_root,
    resolve_private_path,
    sanitise_filename,
)


def test_attachment_storage_is_namespaced_per_client(settings, tmp_path):
    settings.PRIVATE_STORAGE_ROOT = tmp_path
    settings.MEDIA_ROOT = tmp_path / "acme"
    acme_root = client_storage_root()

    settings.MEDIA_ROOT = tmp_path / "globex"
    globex_root = client_storage_root()

    # Two clients on the same host never share a directory tree.
    assert acme_root != globex_root
    assert globex_root not in acme_root.parents
    assert acme_root not in globex_root.parents


def test_attachments_are_not_reachable_from_a_static_url():
    # There is no MEDIA_URL at all: nothing maps a URL onto the private tree.
    assert settings.MEDIA_URL is None
    assert Path(settings.MEDIA_ROOT) != Path(settings.STATIC_ROOT)


def test_private_storage_refuses_to_produce_a_public_url(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    storage = PrivateStorage()
    with pytest.raises(NotImplementedError, match="no public URL"):
        storage.url("quotations/QT-00001.pdf")


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../etc/passwd",
        "..",
        "quotations/../../../../etc/shadow",
        "/etc/passwd",
    ],
)
def test_path_traversal_is_refused_not_clamped(settings, tmp_path, hostile):
    settings.MEDIA_ROOT = tmp_path / "client"
    with pytest.raises(UnsafePath):
        resolve_private_path(hostile)


def test_a_legitimate_path_resolves_inside_the_scope(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "client"
    resolved = resolve_private_path("quotations", "2026", "QT-00001.pdf")
    assert resolved.is_relative_to(client_storage_root())


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("Purchase Order.pdf", "Purchase_Order.pdf"),
        ("../../etc/passwd", "passwd"),
        (r"C:\Users\me\quote.pdf", "quote.pdf"),
        ("", "file"),
        ("....", "file"),
        # An Arabic file name must keep its extension, not collapse into it.
        ("\u0645\u0644\u0641.pdf", "file.pdf"),
        ("\u0645\u0644\u0641 \u0627\u0644\u0639\u0631\u0636.pdf", "file.pdf"),
        ("archive.tar.gz", "archive.tar.gz"),
        ("report.PDF\x00.exe", "report.PDF.exe"),
    ],
)
def test_uploaded_filenames_are_reduced_to_something_safe(supplied, expected):
    assert sanitise_filename(supplied) == expected


def test_a_very_long_filename_is_truncated_but_keeps_its_extension():
    result = sanitise_filename("a" * 500 + ".pdf")
    assert len(result) <= 120
    assert result.endswith(".pdf")
