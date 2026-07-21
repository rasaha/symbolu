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
    GovernanceRecord, GoverningDecision, SCHEMA_VERSION,
)

__all__ = ["GovernanceTruthLayer", "GovernanceConfig", "Situation", "BASELINES", "config",
           "GovernanceRecord", "GoverningDecision", "SCHEMA_VERSION"]
