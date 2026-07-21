"""
TAP-E4 behavioral tests (Section: behavioral tests).

Cover: basic governing selection, jurisdiction/scope filtering, expired/superseded/future
rejection, version recency, draft non-selectability, customer-contract override, emergency
override, law supremacy (law never overridden by a contract/policy), exception handling,
conflict surfacing, no-governing gaps, upstream-gap preservation, provenance completeness,
independent critical-failure accounting, determinism, schema validation, and rejection of
malformed input. TAP-E1/E2/E3 are consumed through frozen public interfaces only.
"""

import json

import pytest

from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1c
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e4_governance_truth import (
    BASELINES, GovernanceTruthLayer, Situation, config,
)
from truth_assurance_pipeline.tap_e4_governance_truth import harness, loader, metrics
from truth_assurance_pipeline.tap_e4_governance_truth.authority import AuthorityTier
from truth_assurance_pipeline.tap_e4_governance_truth.corpus import cases as corpus
from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    GovStatus, validate_record,
)
from truth_assurance_pipeline.tap_e4_governance_truth.validator import validate_inputs

_E1 = IntentUnderstandingLayer(e1c("V4"))
_F = GovernanceTruthLayer(config("F"))


def _resolve(case, cfg="F"):
    intent = _E1.interpret(RawUserRequest(case.case_id, case.request_text))
    ret = corpus.build_retrieval_record(case)
    rel = corpus.build_relationship_record(case)
    layer = GovernanceTruthLayer(config(cfg))
    return intent, ret, rel, layer.resolve(intent, ret, rel, case.situation)


def _case(cid):
    return next(c for c in corpus.ALL_CASES if c.case_id == cid)


def _decision(rec):
    return rec.governing_authorities[0] if rec.governing_authorities else None


# --------------------------------------------------------------------------- #

def test_basic_governing():
    _, _, _, rec = _resolve(_case("E4D01"))
    d = _decision(rec)
    assert d.selected_authority == "acme refund policy"
    assert d.status == GovStatus.GOVERNING


def test_jurisdiction_filters_out_of_jurisdiction():
    _, _, _, rec = _resolve(_case("E4D02"))
    assert _decision(rec).selected_authority == "acme us privacy policy"


def test_scope_filters_wrong_role():
    _, _, _, rec = _resolve(_case("E4D03"))
    assert _decision(rec).selected_authority == "acme engineer policy"


def test_expired_never_selected():
    _, _, _, rec = _resolve(_case("E4D04"))
    assert _decision(rec).selected_authority == "acme retention policy"


def test_superseded_never_selected():
    _, _, _, rec = _resolve(_case("E4D05"))
    assert _decision(rec).selected_authority == "delta data policy"


def test_future_not_effective_today():
    _, _, _, rec = _resolve(_case("E4D06"))
    assert _decision(rec).selected_authority == "alpha vendor policy"


def test_version_recency():
    _, _, _, rec = _resolve(_case("E4D07"))
    assert _decision(rec).selected_authority == "alpha metrics policy"


def test_draft_not_selectable():
    _, _, _, rec = _resolve(_case("E4D08"))
    d = _decision(rec)
    assert d.selected_authority == "approved security policy"
    assert d.tier != AuthorityTier.DRAFT


def test_customer_contract_override():
    _, _, _, rec = _resolve(_case("E4D09"))
    assert _decision(rec).selected_authority == "acme service agreement"


def test_emergency_override():
    _, _, _, rec = _resolve(_case("E4D10"))
    assert _decision(rec).selected_authority == "alpha emergency procedure"


def test_law_not_overridden_by_contract():
    _, _, _, rec = _resolve(_case("E4D11"))
    d = _decision(rec)
    assert d.selected_authority == "federal breach law"
    assert d.tier == AuthorityTier.LAW


def test_exception_yields_governing_with_exception():
    _, _, _, rec = _resolve(_case("E4D12"))
    d = _decision(rec)
    assert d.status == GovStatus.GOVERNING_WITH_EXCEPTION
    assert d.selected_authority is None
    assert d.exception_basis


def test_conflict_is_surfaced_not_silently_resolved():
    _, _, _, rec = _resolve(_case("E4D13"))
    d = _decision(rec)
    assert d.status == GovStatus.CONFLICTED
    assert d.selected_authority is None
    assert len(rec.governance_conflicts) == 1


def test_no_governing_emits_gap():
    _, _, _, rec = _resolve(_case("E4D14"))
    d = _decision(rec)
    assert d.selected_authority is None
    assert any(g.gap_code.value == "NO_GOVERNING_POLICY" for g in rec.governance_gaps)


def test_upstream_gap_preserved():
    _, _, _, rec = _resolve(_case("E4D15"))
    assert _decision(rec).selected_authority == "alpha ops policy"
    assert any(g.gap_code.value == "INSUFFICIENT_UPSTREAM_RELATIONSHIPS"
               for g in rec.governance_gaps)


# --- provenance / schema --------------------------------------------------- #

def test_selected_authority_has_complete_provenance():
    for c in corpus.ALL_CASES:
        _, _, _, rec = _resolve(c)
        d = _decision(rec)
        if d and d.selected_authority:
            assert d.provenance and all(p.is_complete() for p in d.provenance)


def test_record_validates_and_roundtrips():
    for c in corpus.ALL_CASES:
        _, _, _, rec = _resolve(c)
        ok, problems = validate_record(rec)
        assert ok, (c.case_id, problems)
        assert json.loads(rec.to_json())["governance_record_id"] == rec.governance_record_id


def test_confidence_band_floored_by_minimum_component():
    # a conflicted decision must not report HIGH confidence
    _, _, _, rec = _resolve(_case("E4D13"))
    assert rec.confidence_vector.band() in ("LOW", "MEDIUM", "UNRESOLVED")


# --- critical failures on weak baselines ----------------------------------- #

def test_first_match_baseline_triggers_severe_criticals():
    scores = harness.run_config(config("A"), corpus.cases_for_split("dev"))
    agg = metrics.aggregate(scores)
    assert agg["severe_critical_failure_count"] > 0
    assert agg["expired_policy_selection_rate"] > 0


def test_full_baseline_has_zero_criticals_on_both_splits():
    for split in ("dev", "eval"):
        agg = metrics.aggregate(harness.run_config(config("F"),
                                                   corpus.cases_for_split(split)))
        assert agg["severe_critical_failure_count"] == 0
        assert agg["incorrect_override_rate"] == 0
        assert agg["expired_policy_selection_rate"] == 0


# --- selection / verdict --------------------------------------------------- #

def test_full_pipeline_is_simplest_passing_baseline():
    result = harness.run_all()
    assert result["selection"]["selected_config"] == "F"
    assert result["verdict"] == "PASS_WITH_LIMITED_CLAIM"
    # every earlier baseline must fail at least one gate on dev
    passes = result["selection"]["dev_gate_pass"]
    assert passes["F"] is True
    assert not any(passes[n] for n in ("A", "B", "C", "D", "E"))


def test_all_gates_pass_on_locked_eval():
    result = harness.run_all()
    assert result["gates"]["all_pass"] is True


# --- determinism ----------------------------------------------------------- #

def test_deterministic_across_repeats():
    a = harness.run_all()
    b = harness.run_all()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True,
                                                                    default=str)


def test_frozen_components_hash_stable():
    assert harness.frozen_components_hash() == harness.frozen_components_hash()


# --- input validation ------------------------------------------------------ #

def test_validator_accepts_wellformed_inputs():
    c = _case("E4D01")
    intent, ret, rel, _ = _resolve(c)
    ok, problems = validate_inputs(intent, ret, rel)
    assert ok, problems


def test_validator_rejects_mismatched_retrieval_reference():
    c1, c2 = _case("E4D01"), _case("E4D02")
    intent = _E1.interpret(RawUserRequest(c1.case_id, c1.request_text))
    ret = corpus.build_retrieval_record(c2)          # wrong retrieval record
    rel = corpus.build_relationship_record(c1)
    ok, problems = validate_inputs(intent, ret, rel)
    assert not ok


# --- loader is gold-free --------------------------------------------------- #

def test_public_loader_exposes_no_gold():
    for row in loader.load_public("eval"):
        assert "expected_authority" not in row
        assert "policies" in row


def test_baselines_are_six():
    assert [b.name for b in BASELINES] == ["A", "B", "C", "D", "E", "F"]
