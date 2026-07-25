"""Normalization + hashing tests."""

from __future__ import annotations

from ai_hiring.normalization.cleaners import NormalizationProfile, normalize_text
from ai_hiring.normalization.hashing import normalized_hash, raw_hash


def test_line_endings_normalized():
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"


def test_unicode_nfc_normalized():
    # 'é' as e + combining accent -> single NFC codepoint
    decomposed = "cafe\u0301"
    assert normalize_text(decomposed) == "caf\u00e9"


def test_bom_and_zero_width_stripped():
    assert normalize_text("\ufeffhello\u200bworld") == "helloworld"


def test_prose_collapses_tabs_and_repeated_spaces():
    assert normalize_text("a\t\tb   c", NormalizationProfile.PROSE) == "a b c"


def test_prose_strips_trailing_whitespace_per_line():
    assert normalize_text("line1   \nline2\t\n", NormalizationProfile.PROSE) == "line1\nline2"


def test_code_safe_preserves_indentation_and_spacing():
    code = "def f():\n    if x:\n        return  1"
    # code-safe keeps internal runs of spaces (indentation is semantic)
    out = normalize_text(code, NormalizationProfile.CODE_SAFE)
    assert "    if x:" in out
    assert "        return  1" in out  # double space inside code preserved


def test_invalid_utf_is_repaired_not_fatal():
    from ai_hiring.normalization.cleaners import decode_bytes

    text = decode_bytes(b"ok \xff\xfe done")
    assert "ok" in text and "done" in text


def test_normalization_is_idempotent():
    once = normalize_text("a\r\n\tb   c ")
    twice = normalize_text(once)
    assert once == twice


# --- hashing ---------------------------------------------------------------
def test_same_content_same_hash():
    assert raw_hash(b"identical") == raw_hash(b"identical")
    assert raw_hash(b"a") != raw_hash(b"b")


def test_raw_vs_normalized_hash_differ_but_normalized_converges():
    a = "hello   world"
    b = "hello world"
    # raw bytes differ -> different raw hashes
    assert raw_hash(a.encode()) != raw_hash(b.encode())
    # but after prose normalization they converge
    assert normalized_hash(normalize_text(a)) == normalized_hash(normalize_text(b))


def test_whitespace_only_difference_preserves_raw_distinction(platform):
    from ai_hiring.normalization.models import EvidenceFormat, RawSubmission

    svc = platform.evidence_ingestion_service
    s1 = RawSubmission.from_text(
        "answer   here", candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader="svc-ats",
    )
    s2 = RawSubmission.from_text(
        "answer here", candidate_id="c1", role_id="r1", assessment_item_id="a2",
        declared_format=EvidenceFormat.TEXT, uploader="svc-ats",
    )
    i1 = svc.ingest(s1)
    i2 = svc.ingest(s2)
    # normalized hashes converge; raw hashes recorded separately and differ
    assert i1.normalized_hash == i2.normalized_hash
    assert i1.raw_hash != i2.raw_hash
