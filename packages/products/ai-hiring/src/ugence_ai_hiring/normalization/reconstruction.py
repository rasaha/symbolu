"""Deterministic chunk-reconstruction integrity verification.

Verifies that a set of chunks reconstructs normalized content exactly:
contiguous offsets, no overlap/gaps, correct order, declared length matches
content, per-chunk hash matches, all chunks share one evidence version, and the
reconstructed normalized hash matches the expected value. Fails **closed** — no
silent repair.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from .hashing import chunk_hash
from .hashing import normalized_hash as hash_normalized
from .models import EvidenceChunk


@dataclass(frozen=True)
class ReconstructionResult:
    ok: bool
    reason_code: str = ""
    detail: str = ""
    reconstructed_hash: str = ""


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def verify_reconstruction(
    chunks: tuple[EvidenceChunk, ...],
    *,
    expected_normalized_hash: str,
    evidence_id: str,
    version: int,
) -> ReconstructionResult:
    """Validate chunk integrity and exact reconstruction. Never repairs."""
    if not chunks:
        # Empty content legitimately has zero chunks; the caller decides whether
        # empty is acceptable (it is not, for evaluation eligibility).
        reconstructed = hash_normalized("")
        ok = _eq(reconstructed, expected_normalized_hash)
        return ReconstructionResult(
            ok=ok,
            reason_code="" if ok else "HASH_MISMATCH",
            reconstructed_hash=reconstructed,
        )

    ordered = sorted(chunks, key=lambda c: c.index)

    # foreign chunk (wrong evidence/version)
    for c in ordered:
        if c.evidence_id != evidence_id or c.version != version:
            return ReconstructionResult(False, "FOREIGN_CHUNK",
                                        f"chunk {c.chunk_id} does not belong to "
                                        f"{evidence_id} v{version}")

    # contiguous indices, no duplicates/gaps
    if [c.index for c in ordered] != list(range(len(ordered))):
        return ReconstructionResult(False, "CHUNK_INDEX_GAP",
                                    "chunk indices are not contiguous 0..n-1")

    cursor = 0
    for c in ordered:
        if c.offset != cursor:
            return ReconstructionResult(False, "OFFSET_MISMATCH",
                                        f"chunk {c.index} offset {c.offset} != {cursor}")
        if c.length != len(c.text):
            return ReconstructionResult(False, "LENGTH_MISMATCH",
                                        f"chunk {c.index} declared length != text length")
        if not _eq(chunk_hash(c.text), c.hash):
            return ReconstructionResult(False, "CHUNK_HASH_MISMATCH",
                                        f"chunk {c.index} hash does not match its text")
        cursor += c.length

    reconstructed_text = "".join(c.text for c in ordered)
    reconstructed = hash_normalized(reconstructed_text)
    if not _eq(reconstructed, expected_normalized_hash):
        return ReconstructionResult(False, "HASH_MISMATCH",
                                    "reconstructed normalized hash mismatch",
                                    reconstructed_hash=reconstructed)
    return ReconstructionResult(True, reconstructed_hash=reconstructed)
