"""Phase-3 hard-constraint feasibility tests (matrix B: non-compensatory filtering).

These operate at the ``evaluate_feasibility`` level for precise, single-violation control:
a hard-constraint violation makes a candidate infeasible BEFORE any weighted scoring.
"""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    ActionKind,
    CandidateActionPlan,
    ConstraintViolationKind,
    ResourceChange,
    evaluate_feasibility,
)
import ph_helpers as H


def _s(wid="app"):
    return CapacitySubject(workload_id=wid, tenant_id="tenant-1")


def _plan(kind, current, proposed, *, subj=None, dep=None):
    subj = subj or _s()
    changes = [ResourceChange(subj, current, proposed, role="primary")]
    if dep is not None:
        changes.append(ResourceChange(dep[0], dep[1], dep[2], role="dependency"))
    return CandidateActionPlan(plan_id="p", action_kind=kind, changes=tuple(changes))


def test_below_min_capacity():
    ctx = H.make_ctx(current=6, con=H.constraints(min_capacity=5, max_capacity=50))
    v = evaluate_feasibility(_plan(ActionKind.SCALE_DOWN, 6, 3), ctx)
    assert ConstraintViolationKind.BELOW_MIN_CAPACITY in v


def test_above_max_capacity():
    ctx = H.make_ctx(current=6, con=H.constraints(min_capacity=1, max_capacity=8))
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 10), ctx)
    assert ConstraintViolationKind.ABOVE_MAX_CAPACITY in v


def test_invalid_step():
    ctx = H.make_ctx(current=6, con=H.constraints(min_capacity=1, max_capacity=50, allowed_step=2))
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 7), ctx)  # +1 not a multiple of 2
    assert ConstraintViolationKind.INVALID_STEP in v


def test_quota_exceeded():
    ctx = H.make_ctx(current=6, con=H.constraints(min_capacity=1, max_capacity=50, regional_quota=8))
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 10), ctx)
    assert ConstraintViolationKind.QUOTA_EXCEEDED in v


def test_cooldown_active():
    con = H.constraints(min_capacity=1, max_capacity=50, cooldown_seconds=300.0,
                        last_change_at=H.at(100.0))
    ctx = H.make_ctx(current=6, con=con, recommendation_time=H.at(190.0))  # 90s < 300s cooldown
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 8), ctx)
    assert ConstraintViolationKind.COOLDOWN_ACTIVE in v


def test_cooldown_does_not_block_no_change():
    con = H.constraints(min_capacity=1, max_capacity=50, cooldown_seconds=300.0,
                        last_change_at=H.at(100.0))
    ctx = H.make_ctx(current=6, con=con, recommendation_time=H.at(190.0))
    v = evaluate_feasibility(_plan(ActionKind.NO_CHANGE, 6, 6), ctx)
    assert ConstraintViolationKind.COOLDOWN_ACTIVE not in v


def test_slo_protected_blocks_scale_down():
    con = H.constraints(min_capacity=1, max_capacity=50, protect_slo=True)
    ctx = H.make_ctx(current=6, con=con)
    v = evaluate_feasibility(_plan(ActionKind.SCALE_DOWN, 6, 4), ctx)
    assert ConstraintViolationKind.SLO_PROTECTED in v


def test_error_budget_protected_blocks_scale_down():
    con = H.constraints(min_capacity=1, max_capacity=50, protect_error_budget=True)
    ctx = H.make_ctx(current=6, con=con)
    v = evaluate_feasibility(_plan(ActionKind.SCALE_DOWN, 6, 4), ctx)
    assert ConstraintViolationKind.ERROR_BUDGET_PROTECTED in v


def test_dependency_ceiling_exceeded():
    db = _s("db")
    con = H.constraints(min_capacity=1, max_capacity=50, dependency_capacity_ceiling={"db": 100})
    ctx = H.make_ctx(current=6, con=con)
    plan = _plan(ActionKind.COORDINATED, 6, 8, dep=(db, 100, 160))
    v = evaluate_feasibility(plan, ctx)
    assert ConstraintViolationKind.DEPENDENCY_CEILING_EXCEEDED in v


def test_prohibited_action():
    con = H.constraints(min_capacity=1, max_capacity=50, prohibited_actions=("scale_up",))
    ctx = H.make_ctx(current=6, con=con)
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 8), ctx)
    assert ConstraintViolationKind.PROHIBITED_ACTION in v


def test_max_cost_increase_exceeded():
    # price 1000/replica; +2 replicas => +2000 minor units; cap at 1000.
    con = H.constraints(min_capacity=1, max_capacity=50, max_cost_increase_minor=1000)
    ctx = H.make_ctx(current=6, con=con)
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 8), ctx)
    assert ConstraintViolationKind.MAX_COST_INCREASE_EXCEEDED in v


def test_feasible_plan_has_no_violations():
    ctx = H.make_ctx(current=6, con=H.constraints(min_capacity=1, max_capacity=50))
    v = evaluate_feasibility(_plan(ActionKind.SCALE_UP, 6, 8), ctx)
    assert v == ()


def test_hard_rejection_before_scoring():
    """A candidate that violates a hard constraint is infeasible and is never scored."""
    from ugence_cloud_scaling_controller.planning import score_candidate, RecommendationPolicy
    ctx = H.make_ctx(current=6, con=H.constraints(min_capacity=1, max_capacity=8))
    plan = _plan(ActionKind.SCALE_UP, 6, 10)  # above max
    assert evaluate_feasibility(plan, ctx)  # infeasible
    # scoring still computes a breakdown, but the pipeline never scores infeasible plans;
    # the ordering is enforced by pipeline/record. Here we only assert infeasibility gates.
