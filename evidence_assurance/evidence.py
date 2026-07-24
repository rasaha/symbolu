"""Canonical evidence unit + claim (Phase 2). Deterministic, stdlib-only. The evidence dimensions
(support / entailment / alignment / authority / independence / freshness / coverage /
counterevidence) are kept SEPARATE — never collapsed into one score at this layer. Fields cover
provenance, citation lineage, semantic duplication, and per-dimension uncertainty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

EVIDENCE_SCHEMA_VERSION = "ea_evidence_v1"


@dataclass
class EvidenceUnit:
    evidence_id: str
    source_id: str
    source_type: str = "web"              # web | journal | official | vendor | blog | dataset | model_summary
    publisher: str = "unknown"            # origin / owning entity
    retrieval_path: str = "default"       # which retriever/index produced it
    upstream_source_id: Optional[str] = None   # the source this one derives from (None => primary)
    content_ref: str = ""                 # hash/reference to content (NOT raw content)
    claim_ref: str = ""                   # which claim this is offered for
    passage_ref: str = ""                 # which passage was cited/evaluated
    publication_time: float = 0.0         # epoch
    retrieval_time: float = 0.0
    jurisdiction: Optional[str] = None
    domain: str = "general"
    authority_class: str = "unknown"      # official | peer_reviewed | reputable | low | unknown
    primary: bool = True                  # primary vs secondary source
    derivative: bool = False              # derivative (summary/syndication) of another item
    citation_parent: Optional[str] = None # evidence_id it cites/derives from
    citation_chain: List[str] = field(default_factory=list)
    content_hash: str = ""                # for exact-duplicate detection
    semantic_dupe_group: Optional[str] = None  # cluster id for near/semantic duplicates
    provenance_confidence: float = 1.0    # [0,1] confidence in the provenance metadata itself
    # per-dimension states (kept separate; may be UNKNOWN)
    freshness_state: str = "unknown"      # fresh | stale | superseded | unknown
    independence_state: str = "unknown"   # independent | dependent | duplicate | unknown
    support_state: str = "unknown"        # supports | neutral | unknown
    contradiction_state: str = "unknown"  # contradicts | none | unknown
    scope_match_state: str = "unknown"    # exact | narrower | broader | unknown
    evidence_quality: float = 0.5         # [0,1]
    missing_metadata: List[str] = field(default_factory=list)
    uncertainty: float = 0.0


@dataclass
class ClaimUnit:
    claim_id: str
    text: str
    domain: str = "general"
    risk_class: str = "medium"            # low | medium | high | critical
    jurisdiction: Optional[str] = None
    timeframe: Optional[str] = None
    population: Optional[str] = None       # e.g. "studied cohort" vs "individual"
    scope: str = "specific"                # specific | broad | universal
    as_of_time: float = 0.0


@dataclass
class EvidenceBundle:
    """All evidence offered for one claim."""
    claim: ClaimUnit
    evidence: List[EvidenceUnit]
    counterevidence: List[EvidenceUnit] = field(default_factory=list)

    def n(self) -> int:
        return len(self.evidence)


def high_risk(claim: ClaimUnit) -> bool:
    return claim.risk_class in ("high", "critical")
