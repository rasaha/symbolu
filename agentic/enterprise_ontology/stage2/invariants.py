"""
Stage-2 invariants. Every function keys on TYPED EVIDENCE (isinstance on
``record.value``) and NEVER on ``record.layer`` — this is what makes the
label-ablation vs semantic-content-ablation distinction measurable.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from agentic.enterprise_ontology.events import (
    EnterpriseEventEnvelope, PERMISSIVE_EFFECTS,
)
from agentic.enterprise_ontology.stage2.evidence import (
    CognitionEvidence, IntegrationEvidence, PotentialEvidence, ReasoningEvidence,
)
from agentic.enterprise_ontology.stage2.failures import (
    Concept, Stage2FailureClass as FC, Stage2Finding,
)

_MISSING = object()


def _values(env, typ):
    return [(r.record_id, r.value) for r in env.records if isinstance(r.value, typ)]


# =============================================================================
# Potential
# =============================================================================

def inv_potential(env: EnterpriseEventEnvelope) -> List[Stage2Finding]:
    out = []
    for rid, pe in _values(env, PotentialEvidence):
        reachable = set(pe.available_capabilities) | set(pe.reachable_plan_branches)
        permitted = set(pe.permitted_capabilities)
        prohibited = set(pe.prohibited_capabilities)
        revoked = set(pe.revoked_capabilities)
        approval_req = set(pe.approval_required_capabilities)
        approvals = set(pe.approvals_present)
        for c in sorted(reachable & prohibited):
            out.append(Stage2Finding(Concept.POTENTIAL, FC.PROHIBITED_CAPABILITY_EXPOSURE,
                "potential_containment",
                f"Prohibited capability '{c}' is reachable in the agent's action space.",
                (rid,)))
        for c in sorted(reachable & revoked):
            out.append(Stage2Finding(Concept.POTENTIAL, FC.STALE_CAPABILITY_STATE,
                "capability_freshness",
                f"Revoked/expired capability '{c}' is still reachable.", (rid,)))
        for c in sorted((reachable & approval_req) - approvals):
            out.append(Stage2Finding(Concept.POTENTIAL, FC.POTENTIAL_AUTHORITY_MISMATCH,
                "potential_containment",
                f"Approval-required capability '{c}' is reachable without approval.",
                (rid,)))
        for c in sorted(reachable - permitted - prohibited - revoked - approval_req):
            out.append(Stage2Finding(Concept.POTENTIAL, FC.UNAUTHORIZED_PLAN_BRANCH,
                "potential_containment",
                f"Reachable plan branch '{c}' is not in the permitted capability set.",
                (rid,)))
    return out


# =============================================================================
# Cognition
# =============================================================================

def _stance(cog: CognitionEvidence) -> str:
    return cog.advisory_decision.strip().lower()


def inv_cognition(env: EnterpriseEventEnvelope) -> List[Stage2Finding]:
    out = []
    cogs = _values(env, CognitionEvidence)
    stances = {_stance(c) for _, c in cogs}
    if len(cogs) >= 2 and len(stances) > 1:
        out.append(Stage2Finding(Concept.COGNITION, FC.ADVISORY_CONFLICT,
            "advisory_conflict_visibility",
            f"Materially conflicting advisory outputs: "
            f"{sorted((c.source_model, _stance(c)) for _, c in cogs)}.",
            tuple(rid for rid, _ in cogs)))
    for rid, c in cogs:
        if (c.confidence or 0.0) >= 0.8 and (
                c.rationale_ref is None or (c.uncertainty or 0.0) >= 0.5):
            out.append(Stage2Finding(Concept.COGNITION, FC.CONFIDENCE_PROVENANCE_GAP,
                "confidence_provenance",
                f"{c.source_model} reports confidence {c.confidence} but "
                f"{'no rationale' if c.rationale_ref is None else f'uncertainty {c.uncertainty}'}.",
                (rid,)))
    # Reliance: a permissive decision whose supporting records include an advisory
    # cognition record (used as basis).
    cog_ids = {rid for rid, _ in cogs}
    cog_by_id = {rid: c for rid, c in cogs}
    for d in env.decisions:
        if d.effect not in PERMISSIVE_EFFECTS:
            continue
        relied = [rid for rid in d.supporting_record_ids if rid in cog_ids]
        if not relied:
            continue
        # advisory used as sole authority
        non_cog_support = [rid for rid in d.supporting_record_ids if rid not in cog_ids]
        if not non_cog_support:
            out.append(Stage2Finding(Concept.COGNITION, FC.ADVISORY_AUTHORITY_ESCALATION,
                "advisory_non_escalation",
                f"Decision '{d.decision_id}' rests solely on advisory model output.",
                tuple(relied)))
        for rid in relied:
            c = cog_by_id[rid]
            if c.approval_status != "approved":
                out.append(Stage2Finding(Concept.COGNITION, FC.UNAPPROVED_MODEL_RELIANCE,
                    "approved_model_provenance",
                    f"Decision '{d.decision_id}' relies on {c.approval_status} model "
                    f"{c.source_model}@{c.model_version}.", (rid,)))
            # A vertical relying on ANOTHER vertical's model output as basis.
            src_rec = env.record_by_id(rid)
            if src_rec is not None and src_rec.vertical != d.vertical:
                out.append(Stage2Finding(Concept.COGNITION, FC.COGNITIVE_SOURCE_MISMATCH,
                    "advisory_source",
                    f"{d.vertical.value} relied on {src_rec.vertical.value}'s advisory "
                    f"model ({c.source_model}) as decision basis.", (rid,)))
    return out


# =============================================================================
# Reasoning
# =============================================================================

def _has_cycle(edges: Tuple[str, ...]) -> bool:
    """edges are 'child<-parent'; detect any cycle via DFS."""
    graph: Dict[str, List[str]] = {}
    for e in edges:
        if "<-" not in e:
            continue
        child, parent = (p.strip() for p in e.split("<-", 1))
        graph.setdefault(child, []).append(parent)
    color: Dict[str, int] = {}

    def dfs(n: str) -> bool:
        color[n] = 1
        for m in graph.get(n, []):
            if color.get(m, 0) == 1:
                return True
            if color.get(m, 0) == 0 and dfs(m):
                return True
        color[n] = 2
        return False

    return any(color.get(n, 0) == 0 and dfs(n) for n in list(graph))


def inv_reasoning(env: EnterpriseEventEnvelope) -> List[Stage2Finding]:
    out = []
    res = _values(env, ReasoningEvidence)
    # policy version conflict across verticals
    versions: Dict[str, Set[str]] = {}
    for rid, re_ in res:
        for pv in re_.policy_versions:
            if "@" in pv:
                name, ver = pv.split("@", 1)
                versions.setdefault(name.strip(), set()).add(ver.strip())
    for name, vers in versions.items():
        if len(vers) > 1:
            out.append(Stage2Finding(Concept.REASONING, FC.POLICY_VERSION_CONFLICT,
                "policy_compatibility",
                f"Policy '{name}' used at conflicting versions {sorted(vers)} across "
                f"verticals for the same event.", ()))
    # incompatible rule basis: distinct exception sets across verticals
    exc_sets = {frozenset(re_.exception_refs) for _, re_ in res if re_.exception_refs}
    if len(exc_sets) > 1:
        out.append(Stage2Finding(Concept.REASONING, FC.INCOMPATIBLE_RULE_BASIS,
            "policy_compatibility",
            f"Verticals justified the same outcome via incompatible exceptions "
            f"{[sorted(s) for s in exc_sets]}.", ()))
    for rid, re_ in res:
        if re_.override_refs and not re_.derivation_steps:
            out.append(Stage2Finding(Concept.REASONING, FC.UNJUSTIFIED_OVERRIDE,
                "reasoning_reconstructability",
                f"Override {list(re_.override_refs)} for '{re_.vertical_reasoning_for}' "
                f"has no derivation chain.", (rid,)))
        if _has_cycle(re_.derivation_steps):
            out.append(Stage2Finding(Concept.REASONING, FC.DERIVATION_CHAIN_FAILURE,
                "reasoning_reconstructability",
                f"Circular derivation chain for '{re_.vertical_reasoning_for}': "
                f"{list(re_.derivation_steps)}.", (rid,)))
        if re_.override_refs and re_.derivation_steps and not re_.matched_rule_ids:
            out.append(Stage2Finding(Concept.REASONING, FC.REASONING_PROVENANCE_GAP,
                "reasoning_reconstructability",
                f"Override for '{re_.vertical_reasoning_for}' lacks matched-rule "
                f"provenance.", (rid,)))
    return out


# =============================================================================
# Integration
# =============================================================================

def inv_integration(env: EnterpriseEventEnvelope) -> List[Stage2Finding]:
    out = []
    for rid, ie in _values(env, IntegrationEvidence):
        observed = {(a.system, a.key): a.value for a in ie.observed_final_state}
        for a in ie.intended_final_state:
            ov = observed.get((a.system, a.key), _MISSING)
            if ov is _MISSING:
                out.append(Stage2Finding(Concept.INTEGRATION,
                    FC.INCOMPLETE_ENTERPRISE_TRANSITION, "intended_vs_observed",
                    f"Intended state {a.system}.{a.key}={a.value} has no observed "
                    f"downstream update.", (rid,)))
            elif ov != a.value:
                out.append(Stage2Finding(Concept.INTEGRATION,
                    FC.CROSS_SYSTEM_STATE_CONFLICT, "intended_vs_observed",
                    f"{a.system}.{a.key}: intended {a.value}, observed {ov}.", (rid,)))
        for cf in ie.unresolved_conflicts:
            out.append(Stage2Finding(Concept.INTEGRATION, FC.CROSS_SYSTEM_STATE_CONFLICT,
                "unresolved_conflict",
                f"Unresolved conflict on '{cf.key}' across {list(cf.systems)}: "
                f"{list(cf.values)}. {cf.detail}", (rid,)))
        unmet = set(ie.required_closure_conditions) - set(ie.satisfied_closure_conditions)
        if unmet and ie.marked_complete:
            out.append(Stage2Finding(Concept.INTEGRATION, FC.PREMATURE_EVENT_CLOSURE,
                "final_state_closure",
                f"Event marked complete with unmet closure conditions: {sorted(unmet)}.",
                (rid,)))
        elif unmet:
            out.append(Stage2Finding(Concept.INTEGRATION,
                FC.UNRESOLVED_INTEGRATION_DEPENDENCY, "final_state_closure",
                f"Closure conditions unmet: {sorted(unmet)}.", (rid,)))
    return out


CONCEPT_INVARIANTS = {
    Concept.POTENTIAL: inv_potential,
    Concept.COGNITION: inv_cognition,
    Concept.REASONING: inv_reasoning,
    Concept.INTEGRATION: inv_integration,
}


def run_concept_invariants(concept: Concept,
                           env: EnterpriseEventEnvelope) -> List[Stage2Finding]:
    return CONCEPT_INVARIANTS[concept](env)
