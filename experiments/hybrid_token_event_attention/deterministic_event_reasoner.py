"""
deterministic_event_reasoner.py — the FROZEN deterministic outcome mapper (H4).

Pure, non-learned rules over the EXACT admitted records, branched by the decision contract
(task family = which question is asked, not a hidden label). It answers exactly when the required
records are present and ABSTAINS when they are not — the same abstention contract the learned arms
face. It also returns the exact evidence_ids it used, so H4 is fully attributable.

Role in the study:
  * H4 arm — "Mistral + deterministic event reasoning, no learned event attention".
  * The H3 − H4 comparison asks whether learned event attention adds anything BEYOND these rules.
  * On lookup / version-selection / chain families the rules are exact (H4 should be strong);
    on soft evidence-interaction families (near-tie authority / support-oppose balance) the rules
    are brittle, which is where learned attention can add value.

This module is deterministic and never mutates a record; it is not "reopened" — it is consumed.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .event_schema import EventRecord, REL, ACTIVE
from .datasets import POLICY_TABLE, N_VERSION, N_TIER, ABSTAIN, CONFLICT, YES, NO


def _by_rel(records: List[EventRecord], rel: int, subject: Optional[int] = None) -> List[EventRecord]:
    out = [r for r in records if r.relation_type == rel]
    if subject is not None:
        out = [r for r in out if r.subject_id == subject]
    return out


def _clamp_role(v: int) -> int:
    return max(0, min(4, v))


def reason(records: List[EventRecord], family: str, subject: int) -> Tuple[int, List[int]]:
    if family == "exact_threshold":
        thr = _by_rel(records, REL["threshold_at"], subject)
        amt = _by_rel(records, REL["has_budget"], subject)
        if not thr or not amt:
            return ABSTAIN, []
        t, a = thr[0], amt[0]
        return (YES if a.normalized_value > t.normalized_value else NO), [t.evidence_id, a.evidence_id]

    if family == "active_policy":
        pol = [r for r in _by_rel(records, REL["governed_by"], subject) if r.status == ACTIVE]
        bud = _by_rel(records, REL["has_budget"], subject)
        if not pol or not bud:
            return ABSTAIN, []
        ver = min(pol[0].version, N_VERSION - 1)
        tier = min(bud[0].normalized_value, N_TIER - 1)
        return _clamp_role(POLICY_TABLE[ver][tier]), [pol[0].evidence_id, bud[0].evidence_id]

    if family == "approval_req_vs_granted":
        rq = _by_rel(records, REL["approval_requested"], subject)
        gr = _by_rel(records, REL["approval_granted"], subject)
        if not rq or not gr:
            return ABSTAIN, []
        return (YES if rq[0].normalized_value == gr[0].normalized_value else NO), \
               [rq[0].evidence_id, gr[0].evidence_id]

    if family == "authoritative_source":
        recs = _by_rel(records, REL["requires_approval"], subject)
        if len(recs) < 1:
            return ABSTAIN, []
        best = max(recs, key=lambda r: r.authority)
        top = [r for r in recs if abs(r.authority - best.authority) < 1e-9]
        if len(top) >= 2 and len({r.normalized_value for r in top}) > 1:
            return CONFLICT, [r.evidence_id for r in top]
        return _clamp_role(best.normalized_value), [best.evidence_id]

    if family == "active_vs_stale":
        recs = [r for r in _by_rel(records, REL["requires_approval"], subject) if r.status == ACTIVE]
        if not recs:
            return ABSTAIN, []
        return _clamp_role(recs[0].normalized_value), [recs[0].evidence_id]

    if family == "supporting_vs_opposing":
        sup = _by_rel(records, REL["authorized_by"], subject)
        opp = _by_rel(records, REL["conflicts_with"], subject)
        ids = [r.evidence_id for r in sup + opp]
        if len(sup) > len(opp):
            return YES, ids
        if len(opp) > len(sup):
            return NO, ids
        return CONFLICT, ids

    if family == "exception_interaction":
        pol = [r for r in _by_rel(records, REL["governed_by"], subject) if r.status == ACTIVE]
        bud = _by_rel(records, REL["has_budget"], subject)
        if not pol or not bud:
            return ABSTAIN, []
        ver = min(pol[0].version, N_VERSION - 1)
        tier = min(bud[0].normalized_value, N_TIER - 1)
        base = _clamp_role(POLICY_TABLE[ver][tier])
        used = [pol[0].evidence_id, bud[0].evidence_id]
        exc = [r for r in _by_rel(records, REL["grants_exception"], subject) if r.status == ACTIVE]
        if exc:
            used.append(exc[0].evidence_id)
            return _clamp_role(exc[0].normalized_value), used
        return base, used

    if family == "multi_record_chain":
        aw = _by_rel(records, REL["awarded_to"], subject)
        if not aw:
            return ABSTAIN, []
        vendor = aw[0].object_id_or_value
        gv = _by_rel(records, REL["governed_by"], vendor)
        if not gv:
            return ABSTAIN, []
        contract = gv[0].object_id_or_value
        gp = [r for r in _by_rel(records, REL["governed_by"], contract) if r.status == ACTIVE]
        bud = _by_rel(records, REL["has_budget"], subject)
        if not gp or not bud:
            return ABSTAIN, []
        ver = min(gp[0].version, N_VERSION - 1)
        tier = min(bud[0].normalized_value, N_TIER - 1)
        return _clamp_role(POLICY_TABLE[ver][tier]), \
               [aw[0].evidence_id, gv[0].evidence_id, gp[0].evidence_id, bud[0].evidence_id]

    if family == "unresolved_conflict":
        recs = [r for r in _by_rel(records, REL["requires_approval"], subject) if r.status == ACTIVE]
        if not recs:
            return ABSTAIN, []
        roles = {r.normalized_value for r in recs}
        if len(roles) > 1:
            return CONFLICT, [r.evidence_id for r in recs]
        return _clamp_role(recs[0].normalized_value), [recs[0].evidence_id]

    if family == "evidence_incomplete":
        pol = [r for r in _by_rel(records, REL["governed_by"], subject) if r.status == ACTIVE]
        req = _by_rel(records, REL["requires_approval"], subject)
        if not pol and not req:
            return ABSTAIN, []
        return ABSTAIN, []

    return ABSTAIN, []
