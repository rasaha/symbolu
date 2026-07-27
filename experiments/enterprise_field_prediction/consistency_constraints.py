"""
consistency_constraints.py — cross-field invariants (§10) with LOGGED deterministic repair.

Enforces contract invariants on a predicted StructuredFinding. Every repair is recorded; silent
mutation is prohibited. Used to test post-hoc consistency repair vs unconstrained prediction.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from experiments.enterprise_output_mapping.outcome_contract import (StructuredFinding, POLICY_MISSING,
    POLICY_CONFLICTED, BUDGET_MISSING, APPROVAL_MISSING)


def check(f: StructuredFinding) -> List[str]:
    """Return the list of violated invariants (empty = consistent)."""
    v = []
    if not f.evidence_complete and (f.policy_status not in (POLICY_MISSING, POLICY_CONFLICTED)
                                    and f.budget_status != BUDGET_MISSING):
        v.append("incomplete_but_fields_confident")
    if f.material_conflict and f.policy_status not in (POLICY_CONFLICTED,):
        v.append("conflict_without_conflicted_policy")
    if f.policy_status == POLICY_MISSING and f.evidence_complete:
        v.append("policy_missing_but_complete")
    return v


def repair(f: StructuredFinding) -> Tuple[StructuredFinding, List[Dict]]:
    """Deterministic repair to the contract's abstention side; logs each change."""
    log = []
    b, p, a, mc, ec = (f.budget_status, f.policy_status, f.approval_status,
                       f.material_conflict, f.evidence_complete)
    if mc and p != POLICY_CONFLICTED:
        log.append({"rule": "conflict⇒policy_conflicted", "from": p, "to": POLICY_CONFLICTED}); p = POLICY_CONFLICTED
    if p in (POLICY_MISSING, POLICY_CONFLICTED) or b == BUDGET_MISSING:
        if ec:
            log.append({"rule": "missing/conflict⇒incomplete", "from": ec, "to": False}); ec = False
    return StructuredFinding(b, p, a, material_conflict=mc, evidence_complete=ec,
                             unauthorized_present=f.unauthorized_present), log
