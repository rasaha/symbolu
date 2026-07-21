"""
TAP-E4 — Governance Resolution.

The fourth TAP research layer. Given an ``IntentRecord`` (TAP-E1), a ``RetrievalRecord``
(TAP-E2), and a ``RelationshipRecord`` (TAP-E3) — all consumed through their frozen public
interfaces — plus an explicit governance ``Situation``, it resolves WHICH documented
authority (rule / policy / regulation / contract / version) governs that situation, with
jurisdiction, scope, temporal/version, supersession, exception, precedence, conflict, gap,
and per-authority provenance.

It does NOT determine factual/claim truth, answer the user, retrieve, discover
relationships, or authorize execution. Governance Resolution = "which documented authority
controls here, and why," never "is this obligation correct / should it be enforced."
"""

from truth_assurance_pipeline.tap_e4_governance_truth.applicability import (
    BASELINES, GovernanceConfig, GovernanceTruthLayer, Situation, config,
)
from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    AUTHORITY_MODEL_VERSION, AuthorityTier, GovConflictType, GovGapCode, GovProvenance,
    GovStatus, GovernanceConfidence, GovernanceConflict, GovernanceGap, GovernanceRecord,
    GoverningDecision, RejectedAuthority, SCHEMA_VERSION, validate_record,
)

# NOTE: the canonical engineering name for this layer is **Governance Resolution**; see
# ``truth_assurance_pipeline.tap_e4_governance_resolution`` for the canonical import path.
# This ``tap_e4_governance_truth`` package name is retained for experiment reproducibility
# (it is embedded in stored manifests, experiment IDs, and the frozen_components_hash).

__all__ = [
    "GovernanceTruthLayer", "GovernanceConfig", "Situation", "BASELINES", "config",
    "GovernanceRecord", "GoverningDecision", "GovernanceConflict", "GovernanceGap",
    "GovProvenance", "GovernanceConfidence", "RejectedAuthority", "GovStatus",
    "GovConflictType", "GovGapCode", "AuthorityTier", "validate_record",
    "SCHEMA_VERSION", "AUTHORITY_MODEL_VERSION",
]
