"""
TAP-E4 — Governance Resolution (canonical import package).

This is the **canonical engineering import path** for the Governance Resolution layer. It is
a thin compatibility / re-export layer only — it contains **no copy of the engine**. Every
symbol below is re-exported *by identity* from the historical, reproducibility-preserving
implementation package ``truth_assurance_pipeline.tap_e4_governance_truth`` (whose directory
name, experiment IDs, stored manifests, and ``frozen_components_hash`` are retained
unchanged).

Canonical import (use this for all new downstream work)::

    from truth_assurance_pipeline.tap_e4_governance_resolution import (
        GovernanceResolver, GovernanceSituation, GovernanceRecord, config,
    )
    rec = GovernanceResolver(config("F")).resolve(intent, retrieval, relationship, situation)

The historical import continues to work unchanged::

    from truth_assurance_pipeline.tap_e4_governance_truth import GovernanceTruthLayer, Situation

Canonical-name aliases are **identical objects** (``is``-equal), not new types: no new
serialized type is introduced, no dataclass field is added or altered, and the schema
version is unchanged.

  * ``GovernanceResolver``  is  ``GovernanceTruthLayer``  (the historical resolver class)
  * ``GovernanceSituation`` is  ``Situation``             (the caller-supplied input record)
  * ``GovernanceDecision``  is  ``GoverningDecision``      (the per-decision structure)

``GovernanceSituation`` is an **explicit caller-visible input contract** — the normalized
operational facts the caller supplies — not hidden ground truth and not a fact source owned
by E4. See ``README.md`` and the E4 experiment docs for the ownership and provenance
contract.
"""

from truth_assurance_pipeline.tap_e4_governance_truth import (
    AUTHORITY_MODEL_VERSION,
    AuthorityTier,
    BASELINES,
    GovConflictType,
    GovGapCode,
    GovProvenance,
    GovStatus,
    GovernanceConfidence,
    GovernanceConfig,
    GovernanceConflict,
    GovernanceGap,
    GovernanceRecord,
    GovernanceTruthLayer,
    GoverningDecision,
    RejectedAuthority,
    SCHEMA_VERSION,
    Situation,
    config,
    validate_record,
)

# --- canonical-name aliases (identical objects; no new types / no schema change) -------
GovernanceResolver = GovernanceTruthLayer
GovernanceSituation = Situation
GovernanceDecision = GoverningDecision

__all__ = [
    # canonical names
    "GovernanceResolver", "GovernanceSituation", "GovernanceDecision",
    # historical public symbols (re-exported by identity)
    "GovernanceTruthLayer", "Situation", "GoverningDecision", "GovernanceConfig",
    "BASELINES", "config", "GovernanceRecord", "GovernanceConflict", "GovernanceGap",
    "GovProvenance", "GovernanceConfidence", "RejectedAuthority", "GovStatus",
    "GovConflictType", "GovGapCode", "AuthorityTier", "validate_record",
    "SCHEMA_VERSION", "AUTHORITY_MODEL_VERSION",
]
