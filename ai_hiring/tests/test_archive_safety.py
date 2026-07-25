"""DOCX/ZIP archive-safety tests."""

from __future__ import annotations

import io
import zipfile

import pytest

from ai_hiring.errors import ArchiveSafetyError, ContentExtractionError
from ai_hiring.normalization.archive_safety import inspect_archive
from ai_hiring.normalization.limits import EvidenceLimits

from .conftest import zip_bytes


def test_not_a_zip_is_malformed():
    with pytest.raises(ContentExtractionError):
        inspect_archive(b"definitely not a zip")


def test_entry_count_limit():
    content = zip_bytes({f"f{i}.txt": b"x" for i in range(5)})
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(content, EvidenceLimits(max_archive_entries=2))


def test_entry_size_limit():
    content = zip_bytes({"big.txt": b"x" * 1000})
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(content, EvidenceLimits(max_entry_bytes=100))


def test_total_uncompressed_limit():
    content = zip_bytes({f"f{i}.txt": b"x" * 500 for i in range(4)})
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(content, EvidenceLimits(max_total_uncompressed_bytes=1000))


def test_compression_ratio_bomb():
    # highly compressible payload -> high ratio
    content = zip_bytes({"bomb.txt": b"\x00" * 100_000})
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(content, EvidenceLimits(max_compression_ratio=5.0))


def test_path_traversal_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", b"x")
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(buf.getvalue())


def test_absolute_path_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("/abs/path.txt", b"x")
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(buf.getvalue())


def test_deep_path_rejected():
    deep = "/".join(["d"] * 30) + "/f.txt"
    content = zip_bytes({deep: b"x"})
    with pytest.raises(ArchiveSafetyError):
        inspect_archive(content, EvidenceLimits(max_path_depth=5))


def test_safe_archive_passes():
    content = zip_bytes({"word/document.xml": b"<xml/>"})
    report = inspect_archive(content)
    assert report.entry_count == 1


def test_oversized_xml_read_blocked():
    from ai_hiring.normalization.archive_safety import read_entry_bounded

    content = zip_bytes({"word/document.xml": b"x" * 5000})
    with pytest.raises(ArchiveSafetyError):
        read_entry_bounded(content, "word/document.xml", EvidenceLimits(max_xml_bytes=100))
