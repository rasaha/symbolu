"""
Evidence-unit and document types for TAP-E2 Trusted Retrieval.

Core philosophy: retrieve EVIDENCE UNITS, not documents. An evidence unit is the
smallest independently citable factual fragment practical for the corpus (here, a
sentence-level fragment). Provenance is supported down to the evidence-unit level.

Stdlib-only, deterministic, frozen dataclasses. Nothing here reads a resolver,
governance engine, claim validator, or any later TAP layer. TAP-E1 is imported only
through its stable public interface, never modified.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple


class DocumentType(str, Enum):
    POLICY = "policy"
    SOP = "sop"
    MANUAL = "manual"
    API_DOC = "api_doc"
    CONTRACT = "contract"
    TECH_SPEC = "tech_spec"
    DESIGN_DOC = "design_doc"
    REGULATORY = "regulatory"


class AuthorityLevel(str, Enum):
    """How authoritative a source is for factual grounding. Ordered."""
    REGULATORY = "regulatory"        # binding external regulation
    OFFICIAL_POLICY = "official"     # current official internal policy/contract
    REFERENCE = "reference"          # manuals, specs, API docs
    DRAFT = "draft"                  # drafts / design docs (not authoritative)
    DEPRECATED = "deprecated"        # superseded / expired


AUTHORITY_RANK: Mapping[AuthorityLevel, int] = {
    AuthorityLevel.REGULATORY: 4,
    AuthorityLevel.OFFICIAL_POLICY: 3,
    AuthorityLevel.REFERENCE: 2,
    AuthorityLevel.DRAFT: 1,
    AuthorityLevel.DEPRECATED: 0,
}

AUTHORITATIVE_LEVELS = frozenset({AuthorityLevel.REGULATORY,
                                  AuthorityLevel.OFFICIAL_POLICY})


class ExtractionMethod(str, Enum):
    SENTENCE_SPLIT = "sentence_split"       # deterministic chunker
    STRUCTURED_FIELD = "structured_field"   # e.g. a table row / metadata field


class RetrievalMethod(str, Enum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    EXPANSION = "expansion"                 # pulled in by candidate expansion


@dataclass(frozen=True)
class EvidenceProvenance:
    """Mandatory provenance for every retrieved evidence unit. No evidence may
    appear without this."""
    source_id: str                          # document id
    source_location: str                    # e.g. "section 3 / sentence 2"
    retrieval_path: Tuple[str, ...]         # pipeline stages that surfaced it
    retrieval_method: RetrievalMethod
    retrieval_score: float
    extraction_method: ExtractionMethod

    def is_complete(self) -> bool:
        return bool(self.source_id and self.source_location
                    and self.retrieval_path and self.extraction_method)

    def to_dict(self) -> Dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_location": self.source_location,
            "retrieval_path": list(self.retrieval_path),
            "retrieval_method": self.retrieval_method.value,
            "retrieval_score": round(self.retrieval_score, 6),
            "extraction_method": self.extraction_method.value,
        }


@dataclass(frozen=True)
class EvidenceUnit:
    """The smallest independently citable factual fragment in the corpus."""
    unit_id: str
    doc_id: str
    text: str
    location: str                           # human-readable in-doc location
    doc_type: DocumentType
    authority: AuthorityLevel
    effective_year: Optional[int]           # for freshness / outdatedness
    superseded_by: Optional[str] = None     # unit_id that supersedes this one
    claim_key: Optional[str] = None         # topic key; two units with the same
    #                                         claim_key + different claim_value conflict
    claim_value: Optional[str] = None
    entities: Tuple[str, ...] = ()          # entities the unit is about
    extraction_method: ExtractionMethod = ExtractionMethod.SENTENCE_SPLIT

    @property
    def is_authoritative(self) -> bool:
        return self.authority in AUTHORITATIVE_LEVELS

    @property
    def is_deprecated(self) -> bool:
        return self.authority is AuthorityLevel.DEPRECATED or self.superseded_by is not None

    def to_public_dict(self) -> Dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "location": self.location,
            "doc_type": self.doc_type.value,
            "authority": self.authority.value,
            "effective_year": self.effective_year,
        }


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    doc_type: DocumentType
    authority: AuthorityLevel
    effective_year: Optional[int]
    units: Tuple[EvidenceUnit, ...] = ()

    def to_meta(self) -> Dict[str, object]:
        return {"doc_id": self.doc_id, "title": self.title,
                "doc_type": self.doc_type.value, "authority": self.authority.value,
                "effective_year": self.effective_year, "n_units": len(self.units)}


def stable_hash(obj: object) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
