"""
Deterministic cross-vertical invariants.

Each invariant is annotated with whether it KEYS ON a layer label and which
layers it uses — this drives the honest ablation in the results doc (does value
come from the twelve labels, or from the epistemic/authority/dependency/
reconciliation metadata?).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from agentic.enterprise_ontology.authority import (
    depends_solely_on_advisory,
    has_authority_basis,
    supporting_records,
)
from agentic.enterprise_ontology.events import (
    DependencyStatus,
    EnterpriseEventEnvelope,
    PERMISSIVE_EFFECTS,
)
from agentic.enterprise_ontology.failure_classes import FailureClass, Finding
from agentic.enterprise_ontology.layers import OntologyLayer
from agentic.enterprise_ontology.records import VerificationState


# --- 1. authority provenance (metadata, NOT layer) --------------------------

def inv_authority_provenance(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    for d in env.decisions:
        if d.effect in PERMISSIVE_EFFECTS and not has_authority_basis(d, env):
            out.append(Finding(
                FailureClass.MISSING_AUTHORITY_BASIS, "authority_provenance",
                f"Permissive decision '{d.decision_id}' ({d.vertical.value}) has "
                f"no authority-bearing supporting record.",
                verticals=(d.vertical,), vertical_reason_code=d.reason_code,
                record_refs=d.supporting_record_ids))
    return out


# --- 2. advisory non-escalation (CORE INVARIANT; metadata, NOT layer) -------

def inv_advisory_non_escalation(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    for d in env.decisions:
        if d.effect in PERMISSIVE_EFFECTS and depends_solely_on_advisory(d, env):
            out.append(Finding(
                FailureClass.ADVISORY_AUTHORITY_ESCALATION, "advisory_non_escalation",
                f"Permissive decision '{d.decision_id}' ({d.vertical.value}) rests "
                f"solely on advisory / declared / interpretive records — advisory "
                f"information may tighten or escalate but may not authorize.",
                verticals=(d.vertical,), vertical_reason_code=d.reason_code,
                record_refs=d.supporting_record_ids))
    return out


# --- 3. purpose consistency (layer PURPOSE) ---------------------------------

def inv_purpose_consistency(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    purpose_records = env.records_in_layer(OntologyLayer.PURPOSE)
    for d in env.decisions:
        if d.effect not in PERMISSIVE_EFFECTS:
            continue
        for r in supporting_records(d, env):
            if r.layer == OntologyLayer.PURPOSE and r.verification != VerificationState.VERIFIED:
                out.append(Finding(
                    FailureClass.MISSING_VERIFIED_PURPOSE, "purpose_consistency",
                    f"Permissive decision '{d.decision_id}' relies on a "
                    f"{r.verification.value} purpose ('{r.value}') that is not "
                    f"independently verified.",
                    verticals=(d.vertical, r.vertical),
                    layers=(OntologyLayer.PURPOSE,),
                    vertical_reason_code=r.reason_code, record_refs=(r.record_id,)))
    # Cross-vertical purpose conflict (distinct objectives, one authoritative).
    objectives = {(r.vertical, str((r.value or {}).get("objective") if isinstance(r.value, dict) else r.value))
                  for r in purpose_records}
    distinct = {o for _, o in objectives}
    if len(distinct) > 1 and any(r.is_authority_bearing for r in purpose_records):
        out.append(Finding(
            FailureClass.PURPOSE_POLICY_VIOLATION, "purpose_consistency",
            f"Verticals hold conflicting purposes for the event: {sorted(distinct)}.",
            verticals=tuple(sorted({r.vertical for r in purpose_records}, key=lambda v: v.value)),
            layers=(OntologyLayer.PURPOSE,)))
    return out


# --- 4. form binding (layers FORM + EXECUTION) ------------------------------

def inv_form_binding(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    for ex in env.executions:
        if ex.executed_form is not None and ex.authorized_form is not None \
                and ex.executed_form != ex.authorized_form:
            out.append(Finding(
                FailureClass.FORM_EXECUTION_MISMATCH, "form_binding",
                f"Execution '{ex.execution_id}' ({ex.system}) executed form "
                f"'{ex.executed_form}' but was authorized only for "
                f"'{ex.authorized_form}'.",
                verticals=(ex.vertical,),
                layers=(OntologyLayer.FORM, OntologyLayer.EXECUTION),
                record_refs=(ex.execution_id,)))
    return out


# --- 5. dependency satisfaction (dependency graph, NOT layer) ---------------

def inv_dependency_satisfaction(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    # A vertical "proceeded" if it executed OR issued a permissive decision.
    executed_verticals = {ex.vertical for ex in env.executions} | {
        d.vertical for d in env.decisions if d.effect in PERMISSIVE_EFFECTS}
    for dep in env.dependencies:
        if dep.status == DependencyStatus.SATISFIED:
            continue
        proceeded = dep.from_vertical in executed_verticals
        if dep.status == DependencyStatus.STALE:
            out.append(Finding(
                FailureClass.STALE_OR_CONFLICTING_EVIDENCE, "dependency_satisfaction",
                f"{dep.from_vertical.value} relied on STALE upstream evidence from "
                f"{dep.to_vertical.value} ({dep.description}).",
                verticals=(dep.from_vertical, dep.to_vertical)))
        if proceeded and dep.status in (DependencyStatus.ABSENT, DependencyStatus.DENIED,
                                        DependencyStatus.STALE, DependencyStatus.PENDING):
            out.append(Finding(
                FailureClass.CROSS_VERTICAL_DEPENDENCY_FAILURE, "dependency_satisfaction",
                f"{dep.from_vertical.value} executed while its dependency on "
                f"{dep.to_vertical.value} was {dep.status.value} ({dep.description}).",
                verticals=(dep.from_vertical, dep.to_vertical),
                record_refs=(dep.requires_record_id,) if dep.requires_record_id else ()))
    return out


# --- 6. core preservation (layer CORE) --------------------------------------

def inv_core_preservation(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    for r in env.records_in_layer(OntologyLayer.CORE):
        preserved = True
        if isinstance(r.value, dict) and r.value.get("preserved") is False:
            preserved = False
        if not preserved:
            out.append(Finding(
                FailureClass.CORE_INVARIANT_BREACH, "core_preservation",
                f"Core invariant '{r.value.get('invariant', r.record_id)}' "
                f"({r.vertical.value}) is not preserved.",
                verticals=(r.vertical,), layers=(OntologyLayer.CORE,),
                vertical_reason_code=r.reason_code, record_refs=(r.record_id,)))
    for d in env.decisions:
        if d.overrides_core_record_id is not None:
            out.append(Finding(
                FailureClass.CORE_INVARIANT_BREACH, "core_preservation",
                f"Decision '{d.decision_id}' ({d.vertical.value}) overrides a "
                f"non-bypassable core invariant.",
                verticals=(d.vertical,), layers=(OntologyLayer.CORE,),
                record_refs=(d.overrides_core_record_id,)))
    return out


# --- 7. universal constraint (layer UNIVERSAL) ------------------------------

def inv_universal_constraint(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    has_local_permit = any(d.effect in PERMISSIVE_EFFECTS for d in env.decisions)
    for r in env.records_in_layer(OntologyLayer.UNIVERSAL):
        if isinstance(r.value, dict) and r.value.get("breached") is True:
            out.append(Finding(
                FailureClass.UNIVERSAL_CONSTRAINT_BREACH, "universal_constraint",
                f"Enterprise-wide constraint '{r.value.get('constraint', r.record_id)}' "
                f"({r.vertical.value}) is breached"
                + (" despite a locally-permitted action." if has_local_permit else "."),
                verticals=(r.vertical,), layers=(OntologyLayer.UNIVERSAL,),
                vertical_reason_code=r.reason_code, record_refs=(r.record_id,)))
    return out


# --- 8. execution vs observation (layers EXECUTION + OBSERVATION) -----------

def inv_execution_observation(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    for ex in env.executions:
        obs = env.record_by_id(ex.observation_ref)
        if obs is not None and obs.value != ex.resulting_state:
            out.append(Finding(
                FailureClass.EXECUTION_OBSERVATION_MISMATCH, "execution_observation",
                f"Observation for '{ex.execution_id}' ({obs.value}) disagrees with "
                f"the system's resulting state ({ex.resulting_state}).",
                verticals=(ex.vertical,),
                layers=(OntologyLayer.EXECUTION, OntologyLayer.OBSERVATION),
                record_refs=(ex.execution_id, obs.record_id)))
    return out


# --- 9. reconciliation (executions across systems, NOT layer) ---------------

def inv_reconciliation(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    by_subject = {}
    for ex in env.executions:
        by_subject.setdefault(ex.subject_key, []).append(ex)
    for subject, exs in by_subject.items():
        states = {str(e.resulting_state) for e in exs}
        if len(states) > 1:
            out.append(Finding(
                FailureClass.STATE_RECONCILIATION_FAILURE, "reconciliation",
                f"Systems disagree on final state of '{subject}': "
                f"{ {e.system: str(e.resulting_state) for e in exs} }.",
                verticals=tuple(sorted({e.vertical for e in exs}, key=lambda v: v.value)),
                record_refs=tuple(e.execution_id for e in exs)))
    if env.reconciliation_status == "failed":
        out.append(Finding(
            FailureClass.STATE_RECONCILIATION_FAILURE, "reconciliation",
            "Event reconciliation status is 'failed'.", ))
    return out


# --- 10. identity authority (layers IDENTITY + AGENCY) ----------------------

def inv_identity_authority(env: EnterpriseEventEnvelope) -> List[Finding]:
    out = []
    executed = {ex.vertical for ex in env.executions}
    permitted = {d.vertical for d in env.decisions if d.effect in PERMISSIVE_EFFECTS}
    acting = executed | permitted
    for r in env.records_in_layer(OntologyLayer.IDENTITY):
        if r.verification in (VerificationState.UNKNOWN, VerificationState.DECLARED,
                              VerificationState.DISPUTED) and r.vertical in acting:
            out.append(Finding(
                FailureClass.IDENTITY_AUTHORITY_VIOLATION, "identity_authority",
                f"{r.vertical.value} acted while identity '{r.value}' was "
                f"{r.verification.value} (not verified).",
                verticals=(r.vertical,),
                layers=(OntologyLayer.IDENTITY, OntologyLayer.AGENCY),
                vertical_reason_code=r.reason_code, record_refs=(r.record_id,)))
    return out


@dataclass(frozen=True)
class InvariantSpec:
    name: str
    fn: Callable[[EnterpriseEventEnvelope], List[Finding]]
    layer_keyed: bool                 # does detection hinge on a layer label?
    layers_used: Tuple[OntologyLayer, ...]


INVARIANTS: Tuple[InvariantSpec, ...] = (
    InvariantSpec("authority_provenance", inv_authority_provenance, False, ()),
    InvariantSpec("advisory_non_escalation", inv_advisory_non_escalation, False, ()),
    InvariantSpec("purpose_consistency", inv_purpose_consistency, True,
                  (OntologyLayer.PURPOSE,)),
    InvariantSpec("form_binding", inv_form_binding, True,
                  (OntologyLayer.FORM, OntologyLayer.EXECUTION)),
    InvariantSpec("dependency_satisfaction", inv_dependency_satisfaction, False, ()),
    InvariantSpec("core_preservation", inv_core_preservation, True,
                  (OntologyLayer.CORE,)),
    InvariantSpec("universal_constraint", inv_universal_constraint, True,
                  (OntologyLayer.UNIVERSAL,)),
    InvariantSpec("execution_observation", inv_execution_observation, True,
                  (OntologyLayer.EXECUTION, OntologyLayer.OBSERVATION)),
    InvariantSpec("reconciliation", inv_reconciliation, False, ()),
    InvariantSpec("identity_authority", inv_identity_authority, True,
                  (OntologyLayer.IDENTITY, OntologyLayer.AGENCY)),
)


def run_all_invariants(env: EnterpriseEventEnvelope) -> List[Finding]:
    findings: List[Finding] = []
    for spec in INVARIANTS:
        findings.extend(spec.fn(env))
    return findings
