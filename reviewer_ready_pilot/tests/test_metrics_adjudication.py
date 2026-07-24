"""M10 tests - metrics (Phase 15) + adjudication (Phase 16)."""
import pytest

from reviewer_ready_pilot import metrics, adjudication as adj


def _rec(rid, aid, ob_a, ob_b=None, agreement=True, override=False, trap="none", is_mock=False,
         actiongate="not_applicable", missing_context=False):
    return {"artifact_id": aid, "reviewer_id": rid, "is_mock": is_mock,
            "stage_a": {"obligation": ob_a, "trap_detected": trap},
            "stage_b": {"obligation": ob_b or ob_a, "agreement": agreement, "override": override,
                        "acceptable_actiongate_outcome": actiongate, "missing_context": missing_context}}


# ---- metrics ----

def test_no_real_records_is_not_evaluated():
    m = metrics.compute([])
    assert m["status"] == metrics.STATUS_NO_HUMAN
    assert m["human_validation"] == metrics.NOT_EVALUATED
    assert m["reviewer_reviewer_agreement"] == metrics.NOT_EVALUATED


def test_mock_records_excluded():
    recs = [_rec("REV-A", "rrp-1", "E3", is_mock=True), _rec("REV-B", "rrp-1", "E3", is_mock=True)]
    m = metrics.compute(recs)
    assert m["status"] == metrics.STATUS_NO_HUMAN
    assert m["mock_records_excluded"] == 2
    assert m["real_records"] == 0


def test_real_records_produce_agreement_not_correctness_claim():
    recs = [_rec("REV-A", "rrp-1", "E3"), _rec("REV-B", "rrp-1", "E3")]
    sysr = {"rrp-1": {"final_obligation": "E3"}}
    m = metrics.compute(recs, sysr)
    assert m["status"] == metrics.STATUS_OK
    assert m["reviewer_reviewer_agreement"] == 1.0
    assert "not a claim" in m["note"].lower() or "not a correctness" in m["human_validation"].lower()


def test_disagreement_taxonomy_safety_direction():
    recs = [_rec("REV-A", "rrp-1", "E1"), _rec("REV-B", "rrp-1", "E4")]
    m = metrics.compute(recs, {"rrp-1": {"final_obligation": "E3"}})
    assert m["disagreement_taxonomy"].get("SAFETY_DIRECTION") == 1


def test_trap_catch_rate_uses_expected_trap():
    recs = [_rec("REV-A", "rrp-1", "E3", trap="self_verification"),
            _rec("REV-B", "rrp-1", "E3", trap="none")]
    m = metrics.compute(recs, {"rrp-1": {"final_obligation": "E3", "expected_trap": "self_verification"}})
    assert m["trap_catch_rate"] == 0.5


# ---- adjudication ----

def test_find_disputes_on_real_disagreement():
    recs = [_rec("REV-A", "rrp-1", "E2"), _rec("REV-B", "rrp-1", "E4")]
    cases = adj.find_disputes(recs)
    assert len(cases) == 1 and cases[0].artifact_id == "rrp-1"


def test_mock_disagreement_not_a_dispute():
    recs = [_rec("REV-A", "rrp-1", "E2", is_mock=True), _rec("REV-B", "rrp-1", "E4", is_mock=True)]
    assert adj.find_disputes(recs) == []


def test_adjudicator_separation_enforced():
    case = adj.AdjudicationCase("rrp-1", ["REV-A", "REV-B"], ["E2", "E4"], "OBLIGATION_LEVEL")
    with pytest.raises(ValueError):
        adj.adjudicate(case, adjudicator_id="REV-A", resolution={"obligation": "E3", "reason": "x"})


def test_resolved_requires_obligation_and_reason():
    case = adj.AdjudicationCase("rrp-1", ["REV-A", "REV-B"], ["E2", "E4"], "OBLIGATION_LEVEL")
    with pytest.raises(ValueError):
        adj.adjudicate(case, adjudicator_id="REV-C", resolution={"obligation": "E3", "reason": ""})
    r = adj.adjudicate(case, adjudicator_id="REV-C", resolution={"obligation": "E3", "reason": "telemetry needed"})
    assert r.outcome == adj.RESOLVED and r.resolved_obligation == "E3"


def test_unresolved_is_valid_terminus():
    case = adj.AdjudicationCase("rrp-1", ["REV-A", "REV-B"], ["E2", "E4"], "OBLIGATION_LEVEL")
    r = adj.adjudicate(case, adjudicator_id="REV-C",
                       resolution={"unresolved": True, "reason": "irreducible domain judgment"})
    assert r.outcome == adj.UNRESOLVED

def test_adjudication_never_fabricates():
    case = adj.AdjudicationCase("rrp-1", ["REV-A", "REV-B"], ["E2", "E4"], "OBLIGATION_LEVEL")
    with pytest.raises(ValueError):
        adj.adjudicate(case, adjudicator_id="REV-C", resolution=None)
