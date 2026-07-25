"""Deterministic evidence chunking.

Splits normalized text into contiguous, non-overlapping character windows so
that concatenating a version's chunks in order reproduces the normalized text
*exactly*. Each chunk records its offset, length, hash, and type.

Chunking is purely mechanical (fixed-size windows); there is no semantic
segmentation, embedding, or scoring here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common import IdFactory, new_id
from .hashing import chunk_hash
from .models import EvidenceChunk

DEFAULT_CHUNK_SIZE = 1000


@dataclass(frozen=True)
class ChunkConfig:
    size: int = DEFAULT_CHUNK_SIZE
    chunk_type: str = "TEXT"


def chunk_text(
    text: str,
    evidence_id: str,
    version: int,
    *,
    config: ChunkConfig = ChunkConfig(),
    id_factory: IdFactory = new_id,
    tenant_id: str = "",
    candidate_id: str = "",
) -> tuple[EvidenceChunk, ...]:
    """Return contiguous chunks that reconstruct ``text`` exactly."""
    if config.size < 1:
        raise ValueError("chunk size must be >= 1")

    chunks: list[EvidenceChunk] = []
    if text == "":
        return ()
    for index, offset in enumerate(range(0, len(text), config.size)):
        piece = text[offset : offset + config.size]
        chunks.append(
            EvidenceChunk(
                chunk_id=id_factory("chunk"),
                evidence_id=evidence_id,
                version=version,
                index=index,
                offset=offset,
                length=len(piece),
                hash=chunk_hash(piece),
                chunk_type=config.chunk_type,
                text=piece,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
            )
        )
    return tuple(chunks)


def reconstruct(chunks: tuple[EvidenceChunk, ...]) -> str:
    """Reassemble normalized text from chunks (inverse of :func:`chunk_text`)."""
    return "".join(c.text for c in sorted(chunks, key=lambda c: c.index))
