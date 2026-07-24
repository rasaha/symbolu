"""M7 tests - assignment (Phase 12) + access control (Phase 12)."""
import pytest

from reviewer_ready_pilot import assignment as asg
from reviewer_ready_pilot.access import AccessController, AccessDenied


def _arts(n=6):
    return [{"artifact_id": f"rrp-{i:02d}", "text": "t", "risk_tier": "low", "claim_family": "x",
             "source_path": f"p/{i}.py", "source_kind": "docstring",
             "gold_obligation": "E1_CONTEXTUAL_SUPPORT"} for i in range(n)]


def _roster():
    return [asg.Reviewer("REV-A", roles={"technical"}), asg.Reviewer("REV-B", roles={"technical", "policy"}),
            asg.Reviewer("REV-C", roles={"domain"})]


def test_each_artifact_gets_quota_reviewers():
    plan = asg.assign(_arts(), _roster())
    for a in plan.assignments:
        assert len(a.reviewer_ids) == asg.REVIEWERS_PER_ARTIFACT
    assert not plan.unassigned


def test_conflict_excluded():
    roster = _roster()
    roster[0].conflicts.add("rrp-00")
    plan = asg.assign(_arts(), roster)
    a0 = next(a for a in plan.assignments if a.artifact_id == "rrp-00")
    assert "REV-A" not in a0.reviewer_ids


def test_required_role_respected():
    plan = asg.assign(_arts(2), _roster(), required_role_for={"rrp-00": "policy"})
    a0 = next(a for a in plan.assignments if a.artifact_id == "rrp-00")
    # only REV-B holds 'policy'; quota of 2 cannot be met -> unassigned recorded, never faked
    assert a0.reviewer_ids == ["REV-B"]
    assert "rrp-00" in plan.unassigned


def test_load_balanced_and_deterministic():
    p1 = asg.assign(_arts(6), _roster())
    p2 = asg.assign(_arts(6), _roster())
    assert p1.as_dict() == p2.as_dict()
    loads = list(p1.per_reviewer_load.values())
    assert max(loads) - min(loads) <= 2


def test_access_denies_unassigned():
    plan = asg.assign(_arts(), _roster())
    ac = AccessController(plan.as_dict(), {r.reviewer_id: "internal" for r in _roster()})
    arts = {a["artifact_id"]: a for a in _arts()}
    # find an artifact REV-A is NOT assigned
    unassigned_to_a = [aid for aid in arts if not ac.can_access("REV-A", aid)]
    assert unassigned_to_a
    with pytest.raises(AccessDenied):
        ac.blinded_view("REV-A", arts[unassigned_to_a[0]])


def test_blinded_view_hides_system_result():
    plan = asg.assign(_arts(), _roster())
    ac = AccessController(plan.as_dict(), {r.reviewer_id: "internal" for r in _roster()})
    arts = {a["artifact_id"]: a for a in _arts()}
    aid = ac.assigned_artifacts("REV-A")[0]
    v = ac.blinded_view("REV-A", arts[aid])
    assert "gold_obligation" not in v


def test_system_result_withheld_until_stage_a_locked():
    plan = asg.assign(_arts(), _roster())
    ac = AccessController(plan.as_dict(), {r.reviewer_id: "internal" for r in _roster()})
    aid = ac.assigned_artifacts("REV-A")[0]
    with pytest.raises(AccessDenied):
        ac.system_result("REV-A", aid, stage_a_locked=False, result={"final_obligation": "E1"})
    ok = ac.system_result("REV-A", aid, stage_a_locked=True, result={"final_obligation": "E1"})
    assert ok["final_obligation"] == "E1"


def test_cross_reviewer_label_read_forbidden():
    plan = asg.assign(_arts(), _roster())
    ac = AccessController(plan.as_dict(), {r.reviewer_id: "internal" for r in _roster()})
    with pytest.raises(AccessDenied):
        ac.read_other_label("REV-A", "REV-B")


def test_tenant_scoping():
    plan = asg.assign(_arts(), _roster())
    ac = AccessController(plan.as_dict(), {"REV-A": "internal", "REV-B": "internal", "REV-C": "internal"})
    assert ac.cross_tenant("REV-A", "internal") is True
    assert ac.cross_tenant("REV-A", "other_tenant") is False
