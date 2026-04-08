"""
Logging Submodule — Phase Quad Explainability & Audit
=====================================================

Enterprise-grade explainability telemetry for Phase Quad.

Components:
    ExplainabilityLogger  — Ring-buffer logger with sink/file support
    AuditTrail            — Compliance-grade append-only audit log
    PhaseQuadExplainer    — Bridge from model internals to telemetry schema
    EnterprisePolicyEngine — "Policies as code" for runtime control
    telemetry_schema      — Data contracts (ExplanationTelemetry, etc.)
"""

from symbolu_core.mechanical.logging.explainability_logger import ExplainabilityLogger
from symbolu_core.mechanical.logging.audit_trail import AuditTrail, AuditEntry
from symbolu_core.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer
from symbolu_core.mechanical.logging.enterprise_policy import (
    EnterprisePolicyEngine,
    PolicyAction,
    PolicyRule,
    PolicyResult,
    PolicyViolation,
)
from symbolu_core.mechanical.logging.telemetry_schema import (
    ExplanationTelemetry,
    PathAttribution,
    AttentionProvenance,
    StabilityMetrics,
    PolicyDecision,
    ProvenanceBlock,
    ConfidenceBand,
    StabilityBadge,
    EscalationLevel,
    PolicyOutcome,
    confidence_to_band,
    stability_to_badge,
)

__all__ = [
    # Logger & Audit
    "ExplainabilityLogger",
    "AuditTrail",
    "AuditEntry",
    # Explainer bridge
    "PhaseQuadExplainer",
    # Enterprise policy
    "EnterprisePolicyEngine",
    "PolicyAction",
    "PolicyRule",
    "PolicyResult",
    "PolicyViolation",
    # Telemetry schema
    "ExplanationTelemetry",
    "PathAttribution",
    "AttentionProvenance",
    "StabilityMetrics",
    "PolicyDecision",
    "ProvenanceBlock",
    "ConfidenceBand",
    "StabilityBadge",
    "EscalationLevel",
    "PolicyOutcome",
    "confidence_to_band",
    "stability_to_badge",
]
