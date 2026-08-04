"""Tests for the local-source intake tool (fail-closed authority control).

Confirms the intake helper records correct provenance for a lawful local source
copy WITHOUT copying it into the repo and WITHOUT leaking the local path, and
that it rejects insufficient/unlawful access methods. It runs no Guna scoring.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

import pytest

_PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "source_intake", _PRODUCT_ROOT / "scripts" / "source_intake.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_record_hashes_without_copying_or_leaking_path(tmp_path):
    mod = _load()
    secret_dir = tmp_path / "very" / "private" / "library"
    secret_dir.mkdir(parents=True)
    src = secret_dir / "muhurta_chintamani_sharma_1996.pdf"
    payload = b"lawful local copy bytes " * 100
    src.write_bytes(payload)

    rec = mod.build_record(
        file_path=str(src),
        source_id="MC-NORMATIVE",
        edition="Muhurta Chintamani, Sharma tr., Sagar 1996",
        acquisition_method="purchased_ebook",
        access_date="2026-08-04",
    )

    # Correct hash + size.
    assert rec["file_sha256"] == hashlib.sha256(payload).hexdigest()
    assert rec["file_size_bytes"] == len(payload)
    # Basename only; the local path must never appear anywhere in the record.
    assert rec["file_basename"] == "muhurta_chintamani_sharma_1996.pdf"
    blob = json.dumps(rec)
    assert str(secret_dir) not in blob
    assert "private" not in blob
    assert rec["local_path"].startswith("OMITTED")
    # It never freezes a source and never copies into the repo.
    assert rec["copied_into_repo"] is False
    assert rec["freeze_status"] == "ACQUIRED_PENDING_TEXT_VERIFICATION"
    # The source file is untouched and no repo copy was made.
    assert src.read_bytes() == payload


def test_rejects_unlawful_or_insufficient_access(tmp_path):
    mod = _load()
    src = tmp_path / "snippet.txt"
    src.write_text("search-result snippet")
    for bad in ("search_snippet", "ai_generated", "unsourced_website", "screenshot"):
        with pytest.raises(ValueError):
            mod.build_record(
                file_path=str(src), source_id="X", edition="e",
                acquisition_method=bad, access_date="2026-08-04",
            )


def test_missing_file_is_rejected():
    mod = _load()
    with pytest.raises(FileNotFoundError):
        mod.build_record(
            file_path="/no/such/file.pdf", source_id="X", edition="e",
            acquisition_method="purchased_ebook", access_date="2026-08-04",
        )


def test_no_source_files_committed_under_rules():
    # Guard: no book/scan/ephemeris binary is committed anywhere under rules/.
    banned = {".pdf", ".epub", ".djvu", ".mobi", ".png", ".jpg", ".jpeg",
              ".tiff", ".se1", ".bsp"}
    offenders = [
        p for p in (_PRODUCT_ROOT / "rules").rglob("*")
        if p.is_file() and p.suffix.lower() in banned
    ]
    assert not offenders, f"unexpected source/binary files committed: {offenders}"
