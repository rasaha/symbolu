"""
Neutral, workflow-agnostic invariants. The SAME functions run over any workflow
(discount, IAM, procurement, onboarding, ...) without change — that reuse is the
scalability claim, measured in shadow.py.

Promotion defaults follow the phased-enforcement guidance: integration closure
and prohibited-capability exposure are the first enforcement candidates;
advisory (Cognition) and derivation (Reasoning) stay audit/warning longer.
"""

from __future__ import annotations

from typing import Dict, List, Set

from agentic.enterprise_governance.model import (
    CapabilityGroup as C, Disposition as D, GovernanceFinding as F,
    PromotionLevel as P, PERMISSIVE, WorkflowEvidence,
)


def _mk(inv, cap, code, detail, disp, prom, refs=()):
    return F(inv, cap, code, detail, disp, prom, tuple(refs))


# 1 — authority provenance
def inv_authority_provenance(wf: WorkflowEvidence) -> List[F]:
    out = []
    by_subject = {e.subject: e for e in wf.evidence}
    for d in wf.decisions:
        if d.effect not in PERMISSIVE:
            continue
        if not any(by_subject.get(s) and by_subject[s].is_authority_bearing
                   for s in d.supporting_refs):
            out.append(_mk("authority_provenance", C.IDENTITY_AUTHORITY,
                "MISSING_AUTHORITY_BASIS",
                f"Permissive decision '{d.decision_id}' has no authority-bearing basis.",
                D.BLOCKING, P.APPROVAL_REQUIRED, (d.decision_id,)))
    return out


# 2 — advisory non-escalation
def inv_advisory_non_escalation(wf: WorkflowEvidence) -> List[F]:
    out = []
    by_subject = {e.subject: e for e in wf.evidence}
    for d in wf.decisions:
        if d.effect not in PERMISSIVE or not d.supporting_refs:
            continue
        recs = [by_subject[s] for s in d.supporting_refs if s in by_subject]
        if recs and not any(r.is_authority_bearing for r in recs) and any(
                r.authority_role.value in ("advisory", "non_authoritative")
                or r.verification.value in ("declared", "unknown", "disputed")
                for r in recs):
            out.append(_mk("advisory_non_escalation", C.ADVISORY_PROVENANCE,
                "ADVISORY_AUTHORITY_ESCALATION",
                f"Decision '{d.decision_id}' rests solely on advisory/declared evidence.",
                D.ESCALATING, P.WARNING, (d.decision_id,)))
    return out


# 3 — capability containment (pre-action)
def inv_capability_containment(wf: WorkflowEvidence) -> List[F]:
    out = []
    for e in wf.by_capability(C.CAPABILITY_SPACE):
        pl = e.payload
        reachable = set(pl.get("available", ())) | set(pl.get("reachable_branches", ()))
        permitted = set(pl.get("permitted", ()))
        prohibited = set(pl.get("prohibited", ()))
        revoked = set(pl.get("revoked", ()))
        approval_req = set(pl.get("approval_required", ()))
        approvals = set(pl.get("approvals_present", ()))
        for c in sorted(reachable & prohibited):
            out.append(_mk("capability_containment", C.CAPABILITY_SPACE,
                "PROHIBITED_CAPABILITY_EXPOSURE",
                f"Prohibited capability '{c}' reachable by {e.subject}.",
                D.PREVENTIVE, P.HARD_ENFORCE, (e.subject,)))
        for c in sorted(reachable & revoked):
            out.append(_mk("capability_containment", C.CAPABILITY_SPACE,
                "STALE_CAPABILITY_STATE",
                f"Revoked capability '{c}' still reachable by {e.subject}.",
                D.PREVENTIVE, P.APPROVAL_REQUIRED, (e.subject,)))
        for c in sorted((reachable & approval_req) - approvals):
            out.append(_mk("capability_containment", C.CAPABILITY_SPACE,
                "CAPABILITY_AUTHORITY_MISMATCH",
                f"Approval-required capability '{c}' reachable without approval.",
                D.PREVENTIVE, P.APPROVAL_REQUIRED, (e.subject,)))
        for c in sorted(reachable - permitted - prohibited - revoked - approval_req):
            out.append(_mk("capability_containment", C.CAPABILITY_SPACE,
                "UNAUTHORIZED_REACHABLE_CAPABILITY",
                f"Reachable capability '{c}' not in permitted set for {e.subject}.",
                D.PREVENTIVE, P.APPROVAL_REQUIRED, (e.subject,)))
    return out


# 4 — purpose verification
def inv_purpose_verified(wf: WorkflowEvidence) -> List[F]:
    out = []
    by_subject = {e.subject: e for e in wf.evidence}
    for d in wf.decisions:
        if d.effect not in PERMISSIVE:
            continue
        for s in d.supporting_refs:
            e = by_subject.get(s)
            if e and e.capability == C.PURPOSE_POLICY_BASIS \
                    and e.verification.value != "verified":
                out.append(_mk("purpose_verified", C.PURPOSE_POLICY_BASIS,
                    "UNVERIFIED_PURPOSE",
                    f"Decision '{d.decision_id}' relies on {e.verification.value} "
                    f"purpose '{e.subject}'.", D.ESCALATING, P.WARNING, (e.subject,)))
    return out


# 5 — policy-version consistency (derivation audit)
def inv_policy_version_consistency(wf: WorkflowEvidence) -> List[F]:
    out = []
    versions: Dict[str, Set[str]] = {}
    for e in wf.by_capability(C.DECISION_DERIVATION):
        for pv in e.payload.get("policy_versions", ()):
            if "@" in pv:
                name, ver = pv.split("@", 1)
                versions.setdefault(name.strip(), set()).add(ver.strip())
    for name, vers in versions.items():
        if len(vers) > 1:
            out.append(_mk("policy_version_consistency", C.DECISION_DERIVATION,
                "POLICY_VERSION_CONFLICT",
                f"Policy '{name}' used at conflicting versions {sorted(vers)}.",
                D.AUDIT_ONLY, P.AUDIT, ()))
    return out


# 6 — form binding
def inv_form_binding(wf: WorkflowEvidence) -> List[F]:
    out = []
    for ex in wf.executions:
        if ex.executed_form is not None and ex.authorized_form is not None \
                and ex.executed_form != ex.authorized_form:
            out.append(_mk("form_binding", C.AUTHORIZED_FORM, "FORM_EXECUTION_MISMATCH",
                f"{ex.system} executed '{ex.executed_form}' but authorized "
                f"'{ex.authorized_form}'.", D.BLOCKING, P.APPROVAL_REQUIRED,
                (ex.execution_id,)))
    return out


# 7 — cross-system reconciliation
def inv_reconciliation(wf: WorkflowEvidence) -> List[F]:
    out = []
    by_subject: Dict[str, list] = {}
    for ex in wf.executions:
        by_subject.setdefault(ex.subject_key, []).append(ex)
    for subject, exs in by_subject.items():
        if len({str(e.resulting_state) for e in exs}) > 1:
            out.append(_mk("reconciliation", C.EXECUTION_OBSERVATION,
                "STATE_RECONCILIATION_FAILURE",
                f"Systems disagree on '{subject}': "
                f"{ {e.system: str(e.resulting_state) for e in exs} }.",
                D.ESCALATING, P.WARNING, tuple(e.execution_id for e in exs)))
    return out


# 8 — dependency satisfaction
def inv_dependency_satisfaction(wf: WorkflowEvidence) -> List[F]:
    out = []
    executed_systems = {ex.system for ex in wf.executions}
    for dep in wf.dependencies:
        if dep.satisfied:
            continue
        if dep.from_system in executed_systems or dep.stale:
            out.append(_mk("dependency_satisfaction", C.EXECUTION_OBSERVATION,
                "CROSS_SYSTEM_DEPENDENCY_FAILURE",
                f"{dep.from_system} proceeded while dependency on {dep.to_system} "
                f"was {'stale' if dep.stale else 'unsatisfied'} ({dep.description}).",
                D.ESCALATING, P.WARNING,
                (dep.requires_subject,) if dep.requires_subject else ()))
    return out


# 9 — cumulative / enterprise-wide constraint
def inv_cumulative_constraint(wf: WorkflowEvidence) -> List[F]:
    out = []
    permissive = any(d.effect in PERMISSIVE for d in wf.decisions)
    for e in wf.by_capability(C.CUMULATIVE_CONSTRAINTS):
        if e.payload.get("breached") is True:
            out.append(_mk("cumulative_constraint", C.CUMULATIVE_CONSTRAINTS,
                "CUMULATIVE_CONSTRAINT_BREACH",
                f"Enterprise-wide constraint '{e.payload.get('constraint', e.subject)}' "
                f"breached" + (" with a locally-permitted action." if permissive else "."),
                D.BLOCKING, P.APPROVAL_REQUIRED, (e.subject,)))
    return out


# 10 — protected invariant preservation
def inv_protected(wf: WorkflowEvidence) -> List[F]:
    out = []
    for e in wf.by_capability(C.PROTECTED_INVARIANTS):
        if e.payload.get("preserved") is False:
            out.append(_mk("protected_invariant", C.PROTECTED_INVARIANTS,
                "PROTECTED_INVARIANT_BREACH",
                f"Protected invariant '{e.payload.get('invariant', e.subject)}' "
                f"not preserved.", D.BLOCKING, P.HARD_ENFORCE, (e.subject,)))
    return out


# 11 — integration / closure
def inv_integration_closure(wf: WorkflowEvidence) -> List[F]:
    out = []
    _MISS = object()
    for e in wf.by_capability(C.INTEGRATION_CLOSURE):
        pl = e.payload
        observed = {(a["system"], a["key"]): a["value"] for a in pl.get("observed", ())}
        for a in pl.get("intended", ()):
            ov = observed.get((a["system"], a["key"]), _MISS)
            if ov is _MISS:
                out.append(_mk("integration_closure", C.INTEGRATION_CLOSURE,
                    "INCOMPLETE_ENTERPRISE_TRANSITION",
                    f"Intended {a['system']}.{a['key']}={a['value']} has no observed "
                    f"update.", D.BLOCKING, P.APPROVAL_REQUIRED, (e.subject,)))
            elif ov != a["value"]:
                out.append(_mk("integration_closure", C.INTEGRATION_CLOSURE,
                    "CROSS_SYSTEM_STATE_CONFLICT",
                    f"{a['system']}.{a['key']}: intended {a['value']}, observed {ov}.",
                    D.BLOCKING, P.APPROVAL_REQUIRED, (e.subject,)))
        unmet = set(pl.get("required_closure", ())) - set(pl.get("satisfied_closure", ()))
        if unmet and wf.marked_complete:
            out.append(_mk("integration_closure", C.INTEGRATION_CLOSURE,
                "PREMATURE_EVENT_CLOSURE",
                f"Workflow marked complete with unmet closure conditions "
                f"{sorted(unmet)}.", D.PREVENTIVE, P.APPROVAL_REQUIRED, (e.subject,)))
        elif unmet:
            out.append(_mk("integration_closure", C.INTEGRATION_CLOSURE,
                "UNRESOLVED_INTEGRATION_DEPENDENCY",
                f"Closure conditions unmet {sorted(unmet)}.", D.ESCALATING,
                P.WARNING, (e.subject,)))
    return out


INVARIANTS = (
    inv_authority_provenance, inv_advisory_non_escalation, inv_capability_containment,
    inv_purpose_verified, inv_policy_version_consistency, inv_form_binding,
    inv_reconciliation, inv_dependency_satisfaction, inv_cumulative_constraint,
    inv_protected, inv_integration_closure,
)


def run_invariants(wf: WorkflowEvidence) -> List[F]:
    out: List[F] = []
    for fn in INVARIANTS:
        out.extend(fn(wf))
    return out
