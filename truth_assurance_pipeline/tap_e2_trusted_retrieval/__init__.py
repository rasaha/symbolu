"""
TAP-E2 — Trusted Retrieval.

The second TAP research layer. It selects candidate EVIDENCE UNITS for downstream truth
reasoning, given an IntentRecord from the FROZEN TAP-E1 layer. It determines *which
evidence should be supplied* — nothing more. It does NOT judge factual correctness,
policy applicability, relationship validity, authorization, claim truth, or response
quality, and it never answers the user.

TAP-E1 is imported through its stable public interface and is never modified.

HONESTY: the corpus is synthetic and author-written for this study; "dense semantic
retrieval" is a DETERMINISTIC concept-vector stand-in, not neural embeddings. Results are
mechanism/construction validation on synthetic text only — not evidence of real-world
retrieval quality or production readiness.
"""

from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    SCHEMA_VERSION, RetrievalRecord, RetrievalQuery, RetrievalGap, GapType,
    RetrievalConfidence, validate_record,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    EvidenceUnit, EvidenceProvenance, Document, DocumentType, AuthorityLevel,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.retrieval import (
    TrustedRetrievalLayer, RetrievalConfig, BASELINES, config,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.index import RetrievalIndex

__all__ = [
    "SCHEMA_VERSION", "RetrievalRecord", "RetrievalQuery", "RetrievalGap", "GapType",
    "RetrievalConfidence", "validate_record",
    "EvidenceUnit", "EvidenceProvenance", "Document", "DocumentType", "AuthorityLevel",
    "TrustedRetrievalLayer", "RetrievalConfig", "BASELINES", "config", "RetrievalIndex",
]

__version__ = "1.0.0"
