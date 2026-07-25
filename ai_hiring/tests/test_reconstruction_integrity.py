"""Deterministic reconstruction-integrity tests."""

from __future__ import annotations

from ai_hiring.normalization.chunking import ChunkConfig, chunk_text, reconstruct
from ai_hiring.normalization.hashing import chunk_hash
from ai_hiring.normalization.hashing import normalized_hash as hnorm
from ai_hiring.normalization.models import EvidenceChunk
from ai_hiring.normalization.reconstruction import verify_reconstruction

TEXT = "A" * 2500  # 3 chunks at size 1000
EVID = "ev-1"


def _chunks(text=TEXT):
    return chunk_text(text, EVID, 1, config=ChunkConfig(size=1000),
                      id_factory=lambda p: f"{p}-x")


def _verify(chunks, text=TEXT, evidence_id=EVID, version=1):
    return verify_reconstruction(chunks, expected_normalized_hash=hnorm(text),
                                 evidence_id=evidence_id, version=version)


def test_exact_round_trip():
    chunks = chunk_text(TEXT, EVID, 1, id_factory=lambda p: f"{p}-x")
    assert reconstruct(chunks) == TEXT
    assert _verify(chunks).ok


def test_reordered_chunks_detected():
    chunks = list(_chunks())
    # swap index labels to simulate reordering corruption
    bad = (chunks[1].model_copy(update={"index": 0}),
           chunks[0].model_copy(update={"index": 1}), chunks[2])
    assert not _verify(bad).ok


def test_missing_chunk_detected():
    chunks = _chunks()
    assert not _verify(chunks[:-1]).ok  # drop last -> gap/hash mismatch


def test_duplicated_chunk_detected():
    chunks = _chunks()
    dup = chunks + (chunks[-1],)
    assert not _verify(dup).ok


def test_overlapping_offsets_detected():
    chunks = list(_chunks())
    bad = (chunks[0], chunks[1].model_copy(update={"offset": 500}), chunks[2])
    assert not _verify(bad).ok


def test_foreign_version_chunk_detected():
    chunks = list(_chunks())
    bad = (chunks[0].model_copy(update={"version": 2}),) + tuple(chunks[1:])
    res = _verify(bad)
    assert not res.ok and res.reason_code == "FOREIGN_CHUNK"


def test_foreign_evidence_chunk_detected():
    chunks = list(_chunks())
    bad = (chunks[0].model_copy(update={"evidence_id": "other"}),) + tuple(chunks[1:])
    assert not _verify(bad).ok


def test_tampered_chunk_hash_detected():
    chunks = list(_chunks())
    bad = (chunks[0].model_copy(update={"hash": "deadbeef"}),) + tuple(chunks[1:])
    res = _verify(bad)
    assert not res.ok and res.reason_code == "CHUNK_HASH_MISMATCH"


def test_final_normalized_hash_mismatch_detected():
    chunks = _chunks()
    res = verify_reconstruction(chunks, expected_normalized_hash="0" * 64,
                                evidence_id=EVID, version=1)
    assert not res.ok and res.reason_code == "HASH_MISMATCH"


def test_service_reconstruction_validation(platform):
    from .conftest import text_sub

    ing = platform.evidence_ingestion_service.ingest(text_sub("reconstruct me please"))
    result = platform.evidence_validation_service.validate_reconstruction(ing.evidence_id)
    assert result.ok
