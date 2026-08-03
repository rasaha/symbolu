"""Hiring domain — the domain layer built on the Decision Governance kernel.

This package is the stable import surface for the *hiring domain vocabulary and
extension points* (evidence types, capability ontology, rubrics, scoring scales)
that specialize the domain-neutral kernel for hiring. It depends on the kernel
(``ugence_decision_authority``) and never the other way around.

The concrete implementations currently live under ``ugence_ai_hiring`` (the historical
package retained for import stability); this module re-exposes the hiring-domain
contracts so consumers can depend on ``ugence_ai_hiring.hiring`` directly.
"""

from __future__ import annotations

from ugence_ai_hiring.ontology.taxonomy import EvidenceType, is_known_evidence_type
from ugence_ai_hiring.ontology.capability import Capability
from ugence_ai_hiring.rubrics.rubric import Rubric, RubricCapability
from ugence_ai_hiring.rubrics.scoring_scale import ScaleType, ScoringScale
from ugence_ai_hiring.rubrics.evidence_rules import EvidenceRule

__all__ = [
    "EvidenceType",
    "is_known_evidence_type",
    "Capability",
    "Rubric",
    "RubricCapability",
    "ScaleType",
    "ScoringScale",
    "EvidenceRule",
]
