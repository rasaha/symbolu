"""Phase-3 operating-constraint and candidate-plan construction tests."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    ActionKind,
    CandidateActionPlan,
    CandidateError,
    ConstraintError,
    OperatingConstraints,
    ResourceChange,
    generate_candidates,
)
import ph_helpers as H


def _s(wid="app"):
    return CapacitySubject(workload_id=wid, tenant_id="tenant-1")


# --- OperatingConstraints ------------------------------------------------------------

def test_min_gt_max_rejected():
    with pytest.raises(ConstraintError):
        OperatingConstraints(min_capacity=10, max_capacity=5)


def test_negative_min_rejected():
    with pytest.raises(ConstraintError):
        OperatingConstraints(min_capacity=-1, max_capacity=5)


def test_step_below_one_rejected():
    with pytest.raises(ConstraintError):
        OperatingConstraints(min_capacity=1, max_capacity=5, allowed_step=0)


def test_quota_below_min_is_not_a_construction_error():
    # A quota below min is a genuine misconfiguration reported by the pipeline as a typed
    # QUOTA_CONFLICT abstention at decision time, not a construction error here.
    c = OperatingConstraints(min_capacity=5, max_capacity=10, regional_quota=3)
    assert c.regional_quota == 3


def test_safety_margin_out_of_range_rejected():
    with pytest.raises(ConstraintError):
        OperatingConstraints(min_capacity=1, max_capacity=5, safety_margin_fraction=1.5)


def test_effective_ceiling_uses_quota():
    c = OperatingConstraints(min_capacity=1, max_capacity=50, regional_quota=20)
    assert c.effective_ceiling() == 20


def test_constraints_round_trip():
    c = OperatingConstraints(min_capacity=1, max_capacity=50, allowed_step=2,
                             regional_quota=40, cooldown_seconds=120.0,
                             dependency_capacity_ceiling={"db": 200},
                             prohibited_actions=("scale_down",), max_cost_increase_minor=10000,
                             safety_margin_fraction=0.1)
    c2 = OperatingConstraints.from_dict(c.to_canonical_dict())
    assert c2.digest() == c.digest()


def test_constraints_from_dict_unknown_field_rejected():
    c = OperatingConstraints(min_capacity=1, max_capacity=5)
    d = c.to_canonical_dict()
    d["surprise"] = 1
    with pytest.raises(ConstraintError):
        OperatingConstraints.from_dict(d)


# --- CandidateActionPlan -------------------------------------------------------------

def test_no_change_with_nonzero_delta_rejected():
    with pytest.raises(CandidateError):
        CandidateActionPlan(plan_id="x", action_kind=ActionKind.NO_CHANGE,
                            changes=(ResourceChange(_s(), 4, 6, role="primary"),))


def test_scale_up_requires_positive_delta():
    with pytest.raises(CandidateError):
        CandidateActionPlan(plan_id="x", action_kind=ActionKind.SCALE_UP,
                            changes=(ResourceChange(_s(), 4, 4, role="primary"),))


def test_scale_down_requires_negative_delta():
    with pytest.raises(CandidateError):
        CandidateActionPlan(plan_id="x", action_kind=ActionKind.SCALE_DOWN,
                            changes=(ResourceChange(_s(), 4, 6, role="primary"),))


def test_coordinated_requires_two_changes():
    with pytest.raises(CandidateError):
        CandidateActionPlan(plan_id="x", action_kind=ActionKind.COORDINATED,
                            changes=(ResourceChange(_s(), 4, 6, role="primary"),))


def test_plan_requires_exactly_one_primary():
    with pytest.raises(CandidateError):
        CandidateActionPlan(plan_id="x", action_kind=ActionKind.COORDINATED, changes=(
            ResourceChange(_s("a"), 4, 6, role="primary"),
            ResourceChange(_s("b"), 4, 6, role="primary"),
        ))


def test_negative_capacity_rejected():
    with pytest.raises(CandidateError):
        ResourceChange(_s(), -1, 6, role="primary")


def test_plan_round_trip():
    p = CandidateActionPlan(plan_id="up", action_kind=ActionKind.SCALE_UP,
                            changes=(ResourceChange(_s(), 4, 8, role="primary"),))
    p2 = CandidateActionPlan.from_dict(p.to_canonical_dict())
    assert p2.digest() == p.digest()


# --- generate_candidates -------------------------------------------------------------

def test_generation_always_includes_no_change():
    plans = generate_candidates(_s(), 6, 8, allowed_step=1, min_capacity=1, max_capacity=50)
    kinds = {p.action_kind for p in plans}
    assert ActionKind.NO_CHANGE in kinds


def test_generation_is_bounded():
    plans = generate_candidates(_s(), 0, 100000, allowed_step=1, min_capacity=0, max_capacity=100000)
    from ugence_cloud_scaling_controller.planning import MAX_CANDIDATES
    assert len(plans) <= MAX_CANDIDATES


def test_generation_respects_step_alignment():
    plans = generate_candidates(_s(), 4, 10, allowed_step=2, min_capacity=0, max_capacity=50)
    for p in plans:
        if p.action_kind is not ActionKind.NO_CHANGE:
            assert p.primary_change.delta % 2 == 0
