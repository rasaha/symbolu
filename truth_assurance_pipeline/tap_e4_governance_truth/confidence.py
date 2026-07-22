"""Multidimensional governance confidence (never one opaque score)."""
from __future__ import annotations

from truth_assurance_pipeline.tap_e4_governance_truth.schema import GovernanceConfidence


def assess(cfg, jurisdiction_conf: float, scope_conf: float, temporal_conf: float,
           exception_conf: float, n_survivors: int, provenance_ok: bool,
           conflicted: bool) -> GovernanceConfidence:
    return GovernanceConfidence(
        authority_confidence=1.0 if n_survivors >= 1 else 0.2,
        jurisdiction_confidence=jurisdiction_conf if cfg.jurisdiction else 0.3,
        scope_confidence=scope_conf,
        temporal_confidence=temporal_conf if cfg.temporal_version else 0.3,
        exception_confidence=exception_conf if cfg.exceptions_precedence else 0.3,
        precedence_confidence=1.0 if cfg.exceptions_precedence else 0.4,
        conflict_confidence=(0.5 if conflicted else 1.0) if cfg.full else 0.4,
        provenance_completeness=1.0 if provenance_ok else 0.0)
