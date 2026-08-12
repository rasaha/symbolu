"""Phase-3 pipeline tests (matrix A: valid recommendations; matrix G: ranking behavior)."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.planning import (
    ActionKind,
    CapacityActionRecommendation,
    DependencyKind,
    RecommendationAbstention,
    RecommendationAbstentionReason as RR,
    recommend_capacity_action,
)
import ph_helpers as H


def _run(fe, st, cb, con, pol=None, **kw):
    kw.setdefault("recommendation_time", H.at(190.0))
    kw.setdefault("validity_seconds", 600.0)
    return recommend_capacity_action(fe, st, cb, con, pol or H.policy(), **kw)


# --- A: valid recommendations --------------------------------------------------------

def test_safe_scale_up():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50))
    assert isinstance(out, CapacityActionRecommendation)
    assert out.selected_plan.action_kind is ActionKind.SCALE_UP
    assert out.selected_plan.primary_change.proposed_capacity == 8
    assert out.estimated_cost_change_minor == 2000


def test_no_change_when_current_covers():
    app = H.subject()
    out = _run(H.build_forecast_evidence(6, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50))
    assert isinstance(out, CapacityActionRecommendation)
    assert out.selected_plan.action_kind is ActionKind.NO_CHANGE


def test_no_change_beats_unnecessary_scaling():
    """Even when a scale-up is feasible, NO_CHANGE wins when current already covers."""
    app = H.subject()
    out = _run(H.build_forecast_evidence(5, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50))
    assert out.selected_plan.action_kind is ActionKind.NO_CHANGE


def test_safe_scale_down_with_cost_eager_policy():
    app = H.subject()
    pol = H.policy(w_change_magnitude=0.0, w_uncertainty=0.0, w_hold_bias=0.0, w_cost=2.0)
    out = _run(H.build_forecast_evidence(3, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(min_capacity=1, max_capacity=50), pol)
    assert isinstance(out, CapacityActionRecommendation)
    assert out.selected_plan.action_kind is ActionKind.SCALE_DOWN
    assert out.estimated_cost_change_minor < 0  # a saving


def test_cheaper_safe_plan_selected():
    """Two covering plans (7 and 8 replicas); the cheaper (7) wins."""
    app = H.subject()
    out = _run(H.build_forecast_evidence(7, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50))
    assert out.selected_plan.primary_change.proposed_capacity == 7


def test_coordinated_multi_resource_plan_prevents_bottleneck():
    app, db = H.subject("app"), H.subject("db")
    topo = H.topology(subj=app, dependency=db, downstream_current=100, required_per_upstream_unit=20.0)
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), topology=topo)
    assert isinstance(out, CapacityActionRecommendation)
    assert out.selected_plan.action_kind is ActionKind.COORDINATED
    assert "bottleneck_removed_by_coordination" in out.reason_codes
    # the coordinated (more expensive) plan is chosen because it's necessary for safety.
    assert out.estimated_cost_change_minor > 2000


def test_more_expensive_necessary_plan_disclosed():
    app, db = H.subject("app"), H.subject("db")
    topo = H.topology(subj=app, dependency=db)
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), topology=topo)
    # cost increase is disclosed and explained.
    assert out.estimated_cost_change_minor > 0
    assert "dependency" in out.dependency_explanation.lower()


def test_bottleneck_transferred_when_dependency_capped():
    app, db = H.subject("app"), H.subject("db")
    topo = H.topology(subj=app, dependency=db)
    con = H.constraints(max_capacity=50, dependency_capacity_ceiling={"db": 100})
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, dependency=db), con, topology=topo)
    assert out.selected_plan.action_kind is ActionKind.SCALE_UP  # coordinated infeasible
    assert "bottleneck_transferred_to_dependency" in out.reason_codes


def test_independent_resource_no_dependency_impact():
    app, other = H.subject("app"), H.subject("logger")
    topo = H.topology(subj=app, dependency=other, kind=DependencyKind.INFORMATIONAL,
                      downstream_current=None, required_per_upstream_unit=None)
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50), topology=topo)
    assert "no_capacity_dependency_considered" in out.reason_codes


# --- G: ranking behavior -------------------------------------------------------------

def test_input_permutation_invariance():
    app, b, c = H.subject("app"), H.subject("b"), H.subject("c")
    from ugence_cloud_scaling_controller.planning import DependencyEdge, DependencyTopology
    e1 = DependencyEdge(app, b, DependencyKind.INFORMATIONAL)
    e2 = DependencyEdge(app, c, DependencyKind.INFORMATIONAL)
    fe = H.build_forecast_evidence(8, subj=app)
    st = H.replicas_state(H.at(180), 6, subj=app)
    cb = H.cost_book(subj=app)
    con = H.constraints(max_capacity=50)
    t1 = DependencyTopology(subject=app, as_of=H.at(120), edges=(e1, e2))
    t2 = DependencyTopology(subject=app, as_of=H.at(120), edges=(e2, e1))
    o1 = _run(fe, st, cb, con, topology=t1)
    o2 = _run(fe, st, cb, con, topology=t2)
    assert o1.digest() == o2.digest()


def test_ambiguous_best_plan_abstains():
    """Zero-weight policy makes two covering plans (7 and 8) tie -> AMBIGUOUS abstention."""
    app = H.subject()
    pol = H.policy(w_coverage=0.0, w_bottleneck_risk=0.0, w_reliability_risk=0.0, w_cost=0.0,
                   w_change_magnitude=0.0, w_uncertainty=0.0, w_hold_bias=0.0, coverage_floor=1.0)
    out = _run(H.build_forecast_evidence(7, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50), pol)
    assert isinstance(out, RecommendationAbstention)
    assert out.reason is RR.AMBIGUOUS_BEST_PLAN


def test_unique_best_plan_selected():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50))
    assert isinstance(out, CapacityActionRecommendation)
    # exactly one plan carries the selected id
    assert sum(1 for ec in out.evaluated_candidates if ec.plan.plan_id == out.selected_plan_id) == 1


def test_score_breakdown_recomputes_from_policy():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(max_capacity=50))
    sb = out.selected.score_breakdown
    # contributions equal sign*weight*feature under the bound policy.
    for f, feat in sb.features.items():
        expected = out.policy.sign_for(f) * out.policy.weight_for(f) * feat
        assert abs(sb.contributions[f] - expected) < 1e-9
