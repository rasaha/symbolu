"""Phase 2 - Formal evidence-obligation model.

The canonical obligation record and vocabularies. An EvidenceObligation answers WHAT evidence standard a
claim must meet - it never asserts the claim is true, never judges whether available evidence is
sufficient (that is EvidenceAssurance), and never authorizes delivery or action.

Fail-closed vocabulary: an unknown or unresolved obligation resolves to INDETERMINATE_OBLIGATION or
HUMAN_REVIEW_REQUIRED, never to a permissive no-gate class.

Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

OBLIGATION_VOCAB_VERSION = "evidence_obligation_vocab_v1"
POLICY_VERSION = "evidence_obligation_policy_v1"

# ---- the 14 canonical evidence-obligation types (never collapsed to a binary flag) --------------
EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED = "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED"
INDEPENDENT_CORROBORATION_REQUIRED = "INDEPENDENT_CORROBORATION_REQUIRED"
INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT = "INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT"
IMPLEMENTATION_EVIDENCE_SUFFICIENT = "IMPLEMENTATION_EVIDENCE_SUFFICIENT"
TELEMETRY_OR_MEASUREMENT_REQUIRED = "TELEMETRY_OR_MEASUREMENT_REQUIRED"
ATTRIBUTION_VERIFICATION_REQUIRED = "ATTRIBUTION_VERIFICATION_REQUIRED"
POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED = "POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED"
LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED = "LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED"
TEMPORAL_VERIFICATION_REQUIRED = "TEMPORAL_VERIFICATION_REQUIRED"
CONTEXTUAL_SUPPORT_SUFFICIENT = "CONTEXTUAL_SUPPORT_SUFFICIENT"
NO_FACTUAL_EVIDENCE_GATE = "NO_FACTUAL_EVIDENCE_GATE"
QUALIFY_BY_DEFAULT = "QUALIFY_BY_DEFAULT"
HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
INDETERMINATE_OBLIGATION = "INDETERMINATE_OBLIGATION"

OBLIGATION_TYPES = (
    EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, INDEPENDENT_CORROBORATION_REQUIRED,
    INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT, IMPLEMENTATION_EVIDENCE_SUFFICIENT,
    TELEMETRY_OR_MEASUREMENT_REQUIRED, ATTRIBUTION_VERIFICATION_REQUIRED,
    POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED, LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED,
    TEMPORAL_VERIFICATION_REQUIRED, CONTEXTUAL_SUPPORT_SUFFICIENT, NO_FACTUAL_EVIDENCE_GATE,
    QUALIFY_BY_DEFAULT, HUMAN_REVIEW_REQUIRED, INDETERMINATE_OBLIGATION,
)

# obligations that permit clean delivery WITHOUT external/independent factual evidence (the utility
# levers). Every one still requires its OWN standard to be met by EvidenceAssurance; none asserts truth.
LOW_EXTERNAL_BURDEN = frozenset({
    INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT, IMPLEMENTATION_EVIDENCE_SUFFICIENT,
    CONTEXTUAL_SUPPORT_SUFFICIENT, NO_FACTUAL_EVIDENCE_GATE,
})
# obligations that REQUIRE independent/external/measured evidence (never satisfiable by the artifact
# itself). These must never be reachable by a low-burden shortcut on a high-risk claim.
HIGH_EXTERNAL_BURDEN = frozenset({
    EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, INDEPENDENT_CORROBORATION_REQUIRED,
    TELEMETRY_OR_MEASUREMENT_REQUIRED, POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
})
# obligations that route to a human rather than an automated evidence check
REVIEW_OR_INDETERMINATE = frozenset({HUMAN_REVIEW_REQUIRED, INDETERMINATE_OBLIGATION})

# ---- supporting vocabularies --------------------------------------------------------------------
RISK_TIERS = ("low", "medium", "high", "critical")
ATTRIBUTION_STATES = ("none", "self_authored", "attributed_third_party", "quoted", "reported")
TEMPORAL_SENSITIVITY = ("static", "slow_changing", "time_sensitive", "current_status")
CLAIM_ACTIONABILITY = ("none", "advisory", "action_proposal", "action_directive")


@dataclass
class EvidenceObligation:
    """The canonical obligation record. Separates: the obligation (what standard applies), from
    available evidence, from sufficiency, from the delivery decision."""
    obligation_id: str
    claim_id: str
    source_artifact_id: str
    # claim characterization
    claim_type: str = ""
    domain: str = ""
    risk_tier: str = "medium"
    intended_use: str = "review"
    # source characterization
    source_role: str = "unknown"
    source_authority: str = "none"
    artifact_authority: str = "none"
    # claim properties
    claim_actionability: str = "none"
    temporal_sensitivity: str = "static"
    jurisdiction_sensitivity: bool = False
    population_sensitivity: bool = False
    attribution_state: str = "none"
    implementation_inspectability: bool = False
    telemetry_dependency: bool = False
    policy_dependency: bool = False
    approval_dependency: bool = False
    # the obligation itself
    evidence_obligation_type: str = INDETERMINATE_OBLIGATION
    minimum_evidence_standard: str = ""
    required_source_classes: List[str] = field(default_factory=list)
    independence_requirement: bool = False
    freshness_requirement: bool = False
    authority_requirement: bool = False
    contradiction_search_requirement: bool = False
    citation_requirement: bool = False
    human_review_requirement: bool = False
    no_evidence_gate_rationale: str = ""
    # meta
    obligation_confidence: float = 0.0
    unresolved_ambiguity: bool = False
    reason_codes: List[str] = field(default_factory=list)
    obligation_vocab_version: str = OBLIGATION_VOCAB_VERSION
    policy_version: str = POLICY_VERSION

    def is_low_external_burden(self) -> bool:
        return self.evidence_obligation_type in LOW_EXTERNAL_BURDEN

    def requires_independent_evidence(self) -> bool:
        return self.evidence_obligation_type in HIGH_EXTERNAL_BURDEN


def new_obligation(claim_id: str, source_artifact_id: str, **kw) -> EvidenceObligation:
    oid = f"obl-{claim_id}"
    return EvidenceObligation(obligation_id=oid, claim_id=claim_id,
                              source_artifact_id=source_artifact_id, **kw)


def validate_obligation(o: EvidenceObligation) -> List[str]:
    """Fail-closed structural validation. Returns violation codes (empty = valid)."""
    v: List[str] = []
    if o.evidence_obligation_type not in OBLIGATION_TYPES:
        v.append("OBL.UNKNOWN_TYPE")
    if o.risk_tier not in RISK_TIERS:
        v.append("OBL.UNKNOWN_RISK")
    # a NO_FACTUAL_EVIDENCE_GATE on a high/critical risk claim is a hard structural error
    if o.evidence_obligation_type == NO_FACTUAL_EVIDENCE_GATE and o.risk_tier in ("high", "critical"):
        v.append("OBL.NO_GATE_ON_HIGH_RISK")
    # low-burden obligation on an actionable proposal must still carry an approval/policy path
    if o.claim_actionability in ("action_proposal", "action_directive") and o.is_low_external_burden():
        v.append("OBL.LOW_BURDEN_ON_ACTION")
    return v
