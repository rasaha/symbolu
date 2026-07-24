"""Phases 24-25 tests: null resolution and the evidence-gated decision."""
from evidence_obligation import architectural_decision as ad


def test_nulls_resolved_mixed():
    m = ad.decide()
    assert m["nulls_total"] == 18
    assert m["nulls_rejected"] >= 10          # concept-validating nulls rejected
    assert m["nulls_retained"] >= 4           # simplification/safety/readiness nulls retained


def test_concept_validated_but_stage_not_justified():
    d = ad.decide()["dimension_findings"]
    assert d["concept_validated"] is True
    assert d["distinct_stage_justified"] is False
    assert d["risk_only_dominates_on_clean_allow"] is True


def test_decision_is_reduce_and_fix_first():
    m = ad.decide()
    assert m["architectural_decision"].startswith("3 REDUCE TO CLAIM-TYPE")
    assert m["pilot_decision"].startswith("D FIX EVIDENCE OBLIGATION FIRST")


def test_key_nulls_retained():
    n = ad.decide()["nulls"]
    for k in ("H0-2_risk_tier_alone", "H0-13_simple_comparator_matches",
              "H0-14_reviewers_disagree_too_much", "H0-17_distinct_stage_unnecessary",
              "H0-18_readiness_still_blocked"):
        assert n[k]["null_rejected"] is False
