"""Phase-3 construction-safety / integrity tests (matrix E).

The recommendation record embeds the authoritative inputs and RECOMPUTES every derived claim
at construction AND at ``from_dict``. These tests tamper with a valid record's canonical dict
and prove each forgery is rejected — a caller cannot pair mismatched evidence, forge a score
or cost, select an unevaluated/non-winning plan, or mutate a frozen record.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from ugence_cloud_scaling_controller.planning import (
    CapacityActionRecommendation,
    RecommendationError,
    recommend_capacity_action,
)
import ph_helpers as H


def _valid_rec():
    app, db = H.subject("app"), H.subject("db")
    topo = H.topology(subj=app, dependency=db)  # yields feasible + infeasible candidates
    out = recommend_capacity_action(
        H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=600.0, topology=topo)
    assert isinstance(out, CapacityActionRecommendation)
    return out


def _rebuild(d):
    return CapacityActionRecommendation.from_dict(d)


def test_valid_round_trip():
    rec = _valid_rec()
    assert _rebuild(rec.to_canonical_dict()).digest() == rec.digest()


def test_determinism_same_inputs_same_digest():
    a, b = _valid_rec(), _valid_rec()
    assert a.digest() == b.digest()


def test_diagnostic_annotation_excluded_from_digest():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["diagnostic_annotation"] = "a human note that must not change identity"
    assert _rebuild(d).digest() == rec.digest()


def test_alternative_order_manipulation_does_not_change_identity():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["evaluated_candidates"] = list(reversed(d["evaluated_candidates"]))
    assert _rebuild(d).digest() == rec.digest()


def test_forged_score_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # Inflate one feasible candidate's score self-consistently, then it won't match recompute.
    for ec in d["evaluated_candidates"]:
        if ec["feasible"]:
            sb = ec["score_breakdown"]
            sb["features"]["coverage"] = 9.0
            sb["contributions"]["coverage"] = 9.0 * 4.0  # w_coverage default 4
            sb["total_score"] = sum(sb["contributions"].values())
            break
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_false_cost_delta_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    for ec in d["evaluated_candidates"]:
        if ec["cost_delta_minor"] != 0:
            ec["cost_delta_minor"] = ec["cost_delta_minor"] + 12345
            break
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_forged_feasibility_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    for ec in d["evaluated_candidates"]:
        if ec["feasible"] and ec["plan"]["action_kind"] != "no_change":
            ec["feasible"] = False
            ec["violations"] = ["below_min_capacity"]
            ec["score_breakdown"] = None
            break
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_selected_plan_absent_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["selected_plan_id"] = "does_not_exist"
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_selected_non_winner_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # Point selection at NO_CHANGE, which is not the winner in this under-covered scenario.
    d["selected_plan_id"] = "no_change"
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_missing_no_change_baseline_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["evaluated_candidates"] = [ec for ec in d["evaluated_candidates"]
                                 if ec["plan"]["action_kind"] != "no_change"]
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_subject_mismatch_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["canonical_state"]["subject"]["workload_id"] = "someone_else"
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_tampered_forecast_cutoff_after_rec_time_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    # Push the embedded forecast cutoff far into the future (after the recommendation time).
    d["forecast_evidence"]["forecast"]["forecast_cutoff"] = H.at(99999)
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_tampered_policy_weight_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["policy"]["w_cost"] = 999.0  # scores no longer match the stored breakdowns
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_missing_required_field_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    del d["policy"]
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_surplus_top_level_field_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["totally_unexpected"] = 1
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_malformed_nested_dict_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["cost_book"]["entries"][0]["unit_price"]["amount_minor"] = -5  # negative money
    with pytest.raises(ValueError):
        _rebuild(d)


def test_non_finite_nested_value_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    for ec in d["evaluated_candidates"]:
        if ec["feasible"]:
            ec["score_breakdown"]["total_score"] = float("inf")
            break
    with pytest.raises(ValueError):
        _rebuild(d)


def test_post_construction_mutation_blocked():
    rec = _valid_rec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.selected_plan_id = "hacked"  # type: ignore[misc]


def test_digest_is_content_identity_not_signature():
    """Two records with identical authoritative content share a digest; a single changed
    authoritative field changes it. (Documented as content identity, not authenticity.)"""
    a = _valid_rec()
    # A different current capacity changes an authoritative input -> different identity.
    app, db = H.subject("app"), H.subject("db")
    b = recommend_capacity_action(
        H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 5, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=600.0,
        topology=H.topology(subj=app, dependency=db))
    assert a.digest() != b.digest()
