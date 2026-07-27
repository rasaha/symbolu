"""
evidence_schema.py — typed EvidenceRecord for normalized facts (§5) + interpretation states.

Every extracted fact becomes an EvidenceRecord carrying its provenance (source span, hash), an
extraction method and confidence, and an INTERPRETATION_STATUS. No INFERRED / AMBIGUOUS / CONFLICTED
record may be presented as EXACT — the normalization validator enforces this before anything reaches
the authoritative ledger.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

# interpretation states (§5)
EXACT, INFERRED, AMBIGUOUS, CONFLICTED, INSUFFICIENT_EVIDENCE = (
    "EXACT", "INFERRED", "AMBIGUOUS", "CONFLICTED", "INSUFFICIENT_EVIDENCE")
INTERP_STATES = (EXACT, INFERRED, AMBIGUOUS, CONFLICTED, INSUFFICIENT_EVIDENCE)

# field ownership (§7)
DETERMINISTIC, INTERPRETED, HYBRID, UNRESOLVED = "DETERMINISTIC", "INTERPRETED", "HYBRID", "UNRESOLVED"

EXTRACT_DETERMINISTIC, EXTRACT_LLM, EXTRACT_ORACLE = "deterministic_parser", "llm", "oracle"


def provenance_hash(source_document_id, source_span, normalized_value) -> str:
    return hashlib.sha256(f"{source_document_id}|{source_span}|{normalized_value}".encode()).hexdigest()[:16]


@dataclass
class EvidenceRecord:
    evidence_id: str
    tenant_id: int
    source_document_id: str
    source_span: str                    # the exact substring the fact was extracted from
    subject_id: int
    relation_type: str
    object_id_or_value: object
    normalized_value: object
    version: int
    status: str
    valid_from: int
    valid_to: int
    authority: Optional[int]
    extraction_method: str
    extraction_confidence: float
    interpretation_status: str
    provenance_hash: str = ""
    field_name: str = ""                # which typed field this record populates

    def __post_init__(self):
        if not self.provenance_hash:
            self.provenance_hash = provenance_hash(self.source_document_id, self.source_span,
                                                   self.normalized_value)

    def as_dict(self):
        return asdict(self)
