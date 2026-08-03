"""Explanation projections (§13).

These functions build frontend-friendly projections of EXISTING AWC outputs. They
invent no reasons: every reason, condition, evidence ref, criterion value and
selection state is copied from AWC result objects. The four candidate selection
states are kept distinct: INELIGIBLE, ELIGIBLE_NOT_SELECTED, SELECTED_PRIMARY,
SELECTED_FALLBACK.
"""
from __future__ import annotations

from typing import Any, Dict, List

import ugence_agent_workforce_composer.api as awc

from ..serialization.canonical import to_jsonable


def eligibility_explanation(role_reports: Dict[str, Any], role_id: str | None = None) -> Dict[str, Any]:
    """Per-role eligibility explanation using ``awc.explain_role_report`` plus the
    raw passed/failed/unknown conditions from each agent result."""
    roles = role_reports if role_id is None else {role_id: role_reports[role_id]}
    out: List[Dict[str, Any]] = []
    for rid, report in roles.items():
        explanation = awc.explain_role_report(report)
        agents = []
        for res in report.results:
            agents.append({
                "agent_id": res.agent_id,
                "agent_version": res.agent_version,
                "state": res.state.value if hasattr(res.state, "value") else str(res.state),
                "passed_conditions": to_jsonable(res.passed_conditions),
                "failed_conditions": to_jsonable(res.failed_conditions),
                "unknown_conditions": to_jsonable(res.unknown_conditions),
                "elimination_reasons": to_jsonable(res.elimination_reasons),
                "evidence_refs": list(res.evidence_refs),
                "policy_refs": list(res.policy_refs),
                "result_fingerprint": res.result_fingerprint,
            })
        out.append({
            "role_id": rid,
            "outcome": report.outcome.value if hasattr(report.outcome, "value") else str(report.outcome),
            "eligible_agent_ids": list(report.eligible_agent_ids),
            "eliminated_agent_ids": list(report.eliminated_agent_ids),
            "indeterminate_agent_ids": list(report.indeterminate_agent_ids),
            "explanation": to_jsonable(explanation),
            "agents": agents,
            "report_fingerprint": report.report_fingerprint,
        })
    return {"roles": out}


def ranking_explanation(rankings) -> Dict[str, Any]:
    """Ranking reconstruction: raw/normalized/weighted criterion contributions,
    tie-break values and evidence refs for every ranked candidate."""
    out: List[Dict[str, Any]] = []
    for ranking in rankings:
        candidates = []
        for cand in ranking.ranked_candidates:
            candidates.append({
                "agent_id": cand.agent_id,
                "agent_version": cand.agent_version,
                "rank": cand.rank,
                "total_score": cand.total_score,
                "tie_group": cand.tie_group,
                "tie_break_values": to_jsonable(cand.tie_break_values),
                "evidence_refs": list(cand.evidence_refs),
                "policy_refs": list(cand.policy_refs),
                "criterion_results": [
                    {
                        "criterion": cr.criterion,
                        "metric": cr.metric,
                        "raw_value": cr.raw_value,
                        "normalized_bp": cr.normalized_bp,
                        "weight_bp": cr.weight_bp,
                        "weighted_contribution_bp": cr.weighted_contribution_bp,
                        "evidence_refs": list(cr.evidence_refs),
                        "explanation": cr.explanation,
                    }
                    for cr in cand.criterion_results
                ],
                "result_fingerprint": cand.result_fingerprint,
            })
        out.append({
            "role_id": ranking.role_id,
            "eligible_candidate_count": ranking.eligible_candidate_count,
            "excluded_candidate_count": ranking.excluded_candidate_count,
            "ranked_candidates": candidates,
            "ranking_fingerprint": ranking.ranking_fingerprint,
        })
    return {"rankings": out}


def _selection_index(pipeline) -> Dict[str, Dict[str, str]]:
    """Map role_id → {"agent_id@version": state} across the four selection states."""
    plan = pipeline.plan
    index: Dict[str, Dict[str, str]] = {}
    # start from eligibility (INELIGIBLE / ELIGIBLE_NOT_SELECTED baseline)
    for rid, report in pipeline.role_reports.items():
        states: Dict[str, str] = {}
        for res in report.results:
            key = f"{res.agent_id}@{res.agent_version}"
            st = res.state.value if hasattr(res.state, "value") else str(res.state)
            states[key] = "ELIGIBLE_NOT_SELECTED" if st == "ELIGIBLE" else "INELIGIBLE"
        index[rid] = states
    # primaries
    for assignment in plan.role_assignments:
        key = f"{assignment.primary_agent_id}@{assignment.primary_agent_version}"
        index.setdefault(assignment.role_id, {})[key] = "SELECTED_PRIMARY"
    # fallbacks
    for fb in plan.role_fallback_plans:
        for cand in fb.candidates:
            key = f"{cand.agent_id}@{cand.agent_version}"
            cur = index.setdefault(fb.role_id, {}).get(key)
            if cur != "SELECTED_PRIMARY":
                index[fb.role_id][key] = "SELECTED_FALLBACK"
    return index


def plan_explanation(pipeline) -> Dict[str, Any]:
    """Plan explanation: why each primary was selected, why eligible candidates
    were not, team constraints/objectives, provider & failure-domain concentration,
    permission proposals, fallback coverage and unfilled roles."""
    plan = pipeline.plan
    selection = _selection_index(pipeline)
    return {
        "plan_state": plan.plan_state.value,
        "workflow_identity": plan.workflow_identity,
        "selection_states": selection,
        "role_assignments": to_jsonable(plan.role_assignments),
        "selection_explanation": to_jsonable(plan.selection_explanation),
        "team_constraint_results": to_jsonable(plan.team_constraint_results),
        "team_objective_results": to_jsonable(plan.team_objective_results),
        "permission_bound_proposals": to_jsonable(plan.permission_bound_proposals),
        "role_fallback_plans": to_jsonable(plan.role_fallback_plans),
        "unfilled_roles": list(plan.unfilled_roles),
        "human_review_requirements": to_jsonable(plan.human_review_requirements),
        "search_statistics": to_jsonable(plan.search_statistics),
        "total_team_score": plan.total_team_score,
        "plan_fingerprint": plan.plan_fingerprint,
    }
