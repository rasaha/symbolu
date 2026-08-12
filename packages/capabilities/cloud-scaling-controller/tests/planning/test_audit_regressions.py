"""Independent regressions for the three audited integrity findings.

Each test reproduces the auditor's successful attack and asserts it now fails closed at
both direct construction and `from_dict`:

  1. candidate-set integrity  — omitted / fabricated / duplicated / surplus candidates and
     recommendations derived from a reduced candidate set;
  2. embedded temporal safety — future / stale / horizon-incompatible embedded evidence;
  3. abstention authority contract — authority_class=ADVISORY, execution_capability=NONE.
"""

from __future__ import annotations

import copy

import pytest

from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    ActionKind,
    CandidateActionPlan,
    CapacityActionRecommendation,
    RecommendationAbstention,
    RecommendationAbstentionReason,
    RecommendationError,
    ResourceChange,
    build_context,
    evaluate_feasibility,
    plan_cost_delta_minor,
    score_candidate,
    recommend_capacity_action,
)
from ugence_cloud_scaling_controller.planning.recommendation import EvaluatedCandidate
import ph_helpers as H


def _valid_rec(current=6, predicted=8):
    app, db = H.subject("app"), H.subject("db")
    out = recommend_capacity_action(
        H.build_forecast_evidence(predicted, subj=app), H.replicas_state(H.at(180), current, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=600.0, topology=H.topology(subj=app, dependency=db))
    assert isinstance(out, CapacityActionRecommendation)
    return out


def _rebuild(d):
    return CapacityActionRecommendation.from_dict(d)


# ================================================================= Finding 1

def test_omitted_candidate_reduced_set_rejected():
    """Dropping a candidate (a reduced candidate set) is rejected even though every
    remaining candidate is internally self-consistent."""
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # remove one non-selected candidate that is otherwise perfectly valid
    victim = next(ec for ec in d["evaluated_candidates"]
                  if ec["plan"]["plan_id"] != rec.selected_plan_id
                  and ec["plan"]["action_kind"] != "no_change")
    d["evaluated_candidates"] = [ec for ec in d["evaluated_candidates"] if ec is not victim]
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_omitting_the_winner_and_repointing_selection_rejected():
    """Dropping the actual winner so a worse feasible plan is presented as selected."""
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    winner_id = rec.selected_plan_id
    # pick a different feasible candidate to fraudulently "select"
    other = next(ec for ec in d["evaluated_candidates"]
                 if ec["feasible"] and ec["plan"]["plan_id"] != winner_id)
    d["evaluated_candidates"] = [ec for ec in d["evaluated_candidates"]
                                 if ec["plan"]["plan_id"] != winner_id]
    d["selected_plan_id"] = other["plan"]["plan_id"]
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_duplicated_candidate_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["evaluated_candidates"].append(copy.deepcopy(d["evaluated_candidates"][0]))
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_fabricated_surplus_candidate_rejected():
    """A correctly-scored candidate for a plan OUTSIDE the canonical generated set is
    rejected as surplus — the per-candidate recompute passes, only the set check catches it."""
    app, db = H.subject("app"), H.subject("db")
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # Build a legitimate-looking extra candidate (scale to 40, far outside the generated
    # 6->8 range) with a correctly recomputed feasibility/cost/score under the real context.
    ctx = build_context(rec.forecast_evidence, rec.current_state, rec.topology,
                        rec.cost_book, rec.constraints, recommendation_time=rec.recommendation_time)
    surplus_plan = CandidateActionPlan(
        plan_id="scale_up_to_40", action_kind=ActionKind.SCALE_UP,
        changes=(ResourceChange(app, ctx.current_capacity, 40, role="primary"),))
    violations = tuple(v.value for v in evaluate_feasibility(surplus_plan, ctx))
    ec = EvaluatedCandidate(
        plan=surplus_plan, feasible=not violations, violations=violations,
        cost_delta_minor=plan_cost_delta_minor(surplus_plan, ctx),
        score_breakdown=(score_candidate(surplus_plan, ctx, rec.policy) if not violations else None))
    d["evaluated_candidates"].append(ec.to_canonical_dict())
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_content_tampered_candidate_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    for ec in d["evaluated_candidates"]:
        if ec["plan"]["action_kind"] == "scale_up":
            ec["plan"]["changes"][0]["proposed_capacity"] += 1  # off the canonical target
            break
    with pytest.raises(RecommendationError):
        _rebuild(d)


# ================================================================= Finding 2

def test_future_current_state_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["canonical_state"]["observed_at"] = H.at(99999)  # after recommendation_time
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_future_topology_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["topology"]["as_of"] = H.at(99999)
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_stale_cost_evidence_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # expire the pricing strictly before the recommendation time (keep until >= from)
    for entry in d["cost_book"]["entries"]:
        entry["effective_from"] = H.at(-200)
        entry["effective_until"] = H.at(-100)
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_expired_forecast_validity_window_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # forecast age (rec_time 190 - cutoff 180 = 10s) now exceeds a 1s operator validity.
    d["constraints"]["forecast_validity_seconds"] = 1.0
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_recommendation_window_beyond_horizon_rejected_by_record():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["validity_seconds"] = 10_000_000.0  # extends far past the forecast horizon
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_direct_construction_future_state_rejected():
    """Finding 2 also holds for DIRECT construction, not only from_dict."""
    app, db = H.subject("app"), H.subject("db")
    rec = _valid_rec()
    future_state = H.replicas_state(H.at(99999), 6, subj=app)  # observed in the future
    with pytest.raises(RecommendationError):
        CapacityActionRecommendation(
            recommendation_id="x", forecast_evidence=rec.forecast_evidence,
            current_state=future_state, cost_book=rec.cost_book, constraints=rec.constraints,
            policy=rec.policy, evaluated_candidates=rec.evaluated_candidates,
            selected_plan_id=rec.selected_plan_id, recommendation_time=rec.recommendation_time,
            validity_seconds=rec.validity_seconds, topology=rec.topology)


# ================================================================= Finding 3

def test_abstention_rejects_non_advisory_authority_class():
    with pytest.raises(RecommendationError):
        RecommendationAbstention(
            subject=H.subject(), reason=RecommendationAbstentionReason.MISSING_FORECAST,
            recommendation_time=H.at(190), authority_class="AUTHORITATIVE")


def test_abstention_rejects_non_none_execution_capability():
    with pytest.raises(RecommendationError):
        RecommendationAbstention(
            subject=H.subject(), reason=RecommendationAbstentionReason.MISSING_FORECAST,
            recommendation_time=H.at(190), execution_capability="INFRASTRUCTURE_MUTATION")


def test_abstention_from_dict_cannot_smuggle_execution_capability():
    app = H.subject()
    out = recommend_capacity_action(
        None, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints(),
        H.policy(), recommendation_time=H.at(190), validity_seconds=600.0)
    d = out.to_canonical_dict()
    d["execution_capability"] = "INFRASTRUCTURE_MUTATION"
    with pytest.raises(RecommendationError):
        RecommendationAbstention.from_dict(d)
