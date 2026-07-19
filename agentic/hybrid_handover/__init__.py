#!/usr/bin/env python3
"""
Hybrid-LLM enterprise handover — the boundary between the in-house O(n) hybrid
tier and the frontier quadratic-model API.

Two tiers:
  * Part 1 (in-house): the O(n) hybrid ingests the confidential long-context
    corpus on-prem, distills grounded evidence, and reconciles long-range
    supersessions — nothing egresses.
  * Part 2 (frontier): reasons over a small, redacted evidence packet — the
    generation the O(n) tier can't do, on a short context that carries no
    confidential values.

The handover between them is a gated, grounded evidence contract, not a vibe:
  - grounding gate     — every span quotes its source verbatim
  - faithfulness gate  — the packet, re-resolved alone, reproduces the verdict
  - redaction gate     — no secret crosses the boundary; map stays in-house

Entry point: ``run_handover``. Runnable demo: ``python -m agentic.hybrid_handover.demo``.

Status: scaffold. The in-house tier here is a deterministic rules-based
stand-in implementing the same interface a HybridPhaseTransformer-backed
extractor would; the gates, redaction, and frontier wiring are production-shaped.
The piece still to be *measured* is extraction faithfulness on real long
documents (today only a 240K-param synthetic needle exists).
"""

from .faithfulness import (
    FaithfulnessReport,
    GroundingReport,
    ground_spans,
    packet_only_reresolve,
)
from .frontier import FrontierModel, MockFrontierModel
from .inhouse import InHouseExtractor
from .pipeline import HandoverRefused, decide_escalation, run_handover
from .redaction import LeakError, assert_no_leak, redact, rehydrate
from .schema import (
    ConflictResolution,
    Corpus,
    Coverage,
    Document,
    EvidencePacket,
    EvidenceSpan,
    HandoverAudit,
    HandoverResult,
    RedactedPacket,
    RedactionMap,
    ResolvedAnswer,
)

__all__ = [
    "Corpus",
    "Document",
    "EvidenceSpan",
    "EvidencePacket",
    "RedactedPacket",
    "RedactionMap",
    "ConflictResolution",
    "ResolvedAnswer",
    "Coverage",
    "HandoverAudit",
    "HandoverResult",
    "InHouseExtractor",
    "FrontierModel",
    "MockFrontierModel",
    "GroundingReport",
    "FaithfulnessReport",
    "ground_spans",
    "packet_only_reresolve",
    "redact",
    "rehydrate",
    "assert_no_leak",
    "LeakError",
    "run_handover",
    "decide_escalation",
    "HandoverRefused",
]
