"""
The two ablations, kept strictly separate, plus metadata-only reproduction.

* label ablation  — retag the concept records to a DIFFERENT layer, keep the
  typed evidence + all metadata. If findings are unchanged, the LABEL is not
  load-bearing.
* content ablation — drop the concept's typed evidence records, keep every
  stage-1 primitive (executions, reconciliation_status, authority metadata). If
  findings drop, the semantic CONTENT is load-bearing.
* metadata reproduction — can the finding be reproduced from stage-1 primitives
  alone? (Honest, concept-specific.)
"""

from __future__ import annotations

from dataclasses import replace
from typing import List

from agentic.enterprise_ontology.events import EnterpriseEventEnvelope
from agentic.enterprise_ontology.invariants import inv_reconciliation
from agentic.enterprise_ontology.layers import OntologyLayer
from agentic.enterprise_ontology.stage2.evidence import (
    CognitionEvidence, IntegrationEvidence, PotentialEvidence, ReasoningEvidence,
)
from agentic.enterprise_ontology.stage2.failures import Concept, Stage2FailureClass as FC
from agentic.enterprise_ontology.stage2.invariants import run_concept_invariants

CONCEPT_EVIDENCE = {
    Concept.POTENTIAL: PotentialEvidence,
    Concept.COGNITION: CognitionEvidence,
    Concept.REASONING: ReasoningEvidence,
    Concept.INTEGRATION: IntegrationEvidence,
}

# A layer deliberately DIFFERENT from each concept's canonical layer, used to
# prove the invariants do not depend on the label.
_WRONG_LAYER = OntologyLayer.EXECUTION


def _is_concept_record(record, concept: Concept) -> bool:
    return isinstance(record.value, CONCEPT_EVIDENCE[concept])


def ablate_label(env: EnterpriseEventEnvelope, concept: Concept) -> EnterpriseEventEnvelope:
    """Retag the concept records to a wrong layer; keep evidence + metadata."""
    new_records = tuple(
        replace(r, layer=_WRONG_LAYER) if _is_concept_record(r, concept) else r
        for r in env.records)
    return replace(env, records=new_records)


def ablate_content(env: EnterpriseEventEnvelope, concept: Concept) -> EnterpriseEventEnvelope:
    """Remove the concept's typed evidence; keep all stage-1 primitives."""
    new_records = tuple(r for r in env.records if not _is_concept_record(r, concept))
    return replace(env, records=new_records)


def metadata_reproduction(concept: Concept, env: EnterpriseEventEnvelope,
                          full_findings: List) -> dict:
    """How much of the concept's value can stage-1 primitives reproduce?"""
    if concept == Concept.POTENTIAL:
        # Stage-1 governs only concrete submitted actions — there is NO pre-action
        # capability-space representation. Nothing reproducible.
        return {"structured_reproduced": 0, "coarse_existence": False,
                "note": "no pre-action capability representation in stage-1"}
    if concept == Concept.COGNITION:
        # Stage-1 authority metadata reproduces only the advisory-cannot-authorize
        # escalation; conflict / model-provenance / confidence gaps are not
        # representable by a single advisory flag.
        repro = sum(1 for f in full_findings
                    if f.failure_class == FC.ADVISORY_AUTHORITY_ESCALATION)
        return {"structured_reproduced": repro, "coarse_existence": repro > 0,
                "note": "only advisory-authorization escalation reproducible"}
    if concept == Concept.REASONING:
        # Flat policy_refs cannot compare versions or reconstruct derivation chains.
        return {"structured_reproduced": 0, "coarse_existence": False,
                "note": "flat policy_refs cannot compare versions or derivations"}
    if concept == Concept.INTEGRATION:
        # Stage-1 reconciliation over executions catches the EXISTENCE of a state
        # disagreement, but not closure conditions / intended state / premature
        # closure (structured).
        coarse = bool(inv_reconciliation(env))
        return {"structured_reproduced": 0, "coarse_existence": coarse,
                "note": "reconciliation flag catches existence, not closure/intent"}
    return {"structured_reproduced": 0, "coarse_existence": False, "note": ""}
