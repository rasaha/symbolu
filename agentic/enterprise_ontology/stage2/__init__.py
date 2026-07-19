"""
Stage-2 targeted validation of the four ontology concepts that did NOT drive
detection in the first pilot: Potential, Cognition, Reasoning, Integration.

Separate extension with its own findings and verdict — it does not alter the
first-pilot conclusion. Self-contained and read-only; imports only stage-1
enterprise-ontology primitives (records/events/layers/verticals), never any
production ActionGate / healthcare / trading / JEPA / sovereign / latent code.

Central discipline: every stage-2 invariant keys on TYPED EVIDENCE CONTENT, never
on `record.layer`. That makes both ablations real measurements:
  * label ablation  — retag the layer, keep the evidence → does the LABEL matter?
  * content ablation — remove the evidence, keep stage-1 metadata → does the
    semantic CONTENT matter?
"""

from agentic.enterprise_ontology.stage2.evidence import (
    CognitionEvidence, IntegrationEvidence, PotentialEvidence, ReasoningEvidence,
    StateAssertion, StateConflict,
)
from agentic.enterprise_ontology.stage2.failures import (
    Concept, Stage2FailureClass, Stage2Finding,
)
from agentic.enterprise_ontology.stage2.invariants import (
    run_concept_invariants, CONCEPT_INVARIANTS,
)
from agentic.enterprise_ontology.stage2.evaluation import run_stage2_evaluation

__all__ = [
    "CognitionEvidence", "IntegrationEvidence", "PotentialEvidence",
    "ReasoningEvidence", "StateAssertion", "StateConflict",
    "Concept", "Stage2FailureClass", "Stage2Finding",
    "run_concept_invariants", "CONCEPT_INVARIANTS", "run_stage2_evaluation",
]
