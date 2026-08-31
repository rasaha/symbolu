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
import dataclasses

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


# ============================================ Hardening item 1: forecast relationship

def _abstention_dict(reason=RecommendationAbstentionReason.MISSING_FORECAST):
    app = H.subject()
    out = recommend_capacity_action(
        None, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints(),
        H.policy(), recommendation_time=H.at(190), validity_seconds=600.0)
    return out.to_canonical_dict()


def test_inflated_forecast_for_rejected():
    """An embedded forecast_for pushed beyond forecast_cutoff + horizon fails closed —
    otherwise a longer validity window would look in-bounds against the inflated endpoint."""
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    orig = d["forecast_evidence"]["forecast"]["forecast_for"]
    d["forecast_evidence"]["forecast"]["forecast_for"] = orig + __import__("datetime").timedelta(seconds=100000)
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_inflated_forecast_for_with_long_validity_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    orig = d["forecast_evidence"]["forecast"]["forecast_for"]
    d["forecast_evidence"]["forecast"]["forecast_for"] = orig + __import__("datetime").timedelta(seconds=100000)
    d["validity_seconds"] = 90000.0  # would fit the inflated endpoint but exceeds the real horizon
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_contradictory_forecast_for_before_cutoff_rejected():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    cutoff = d["forecast_evidence"]["forecast"]["forecast_cutoff"]
    d["forecast_evidence"]["forecast"]["forecast_for"] = cutoff  # equals cutoff, != cutoff + horizon
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_inflated_forecast_for_rejected_on_direct_construction():
    """Item 1 also holds for DIRECT construction, not only from_dict."""
    rec = _valid_rec()
    fc = rec.forecast_evidence.forecast
    bad_fc = dataclasses.replace(
        fc, forecast_for=fc.forecast_for + __import__("datetime").timedelta(seconds=100000))
    bad_evidence = dataclasses.replace(rec.forecast_evidence, forecast=bad_fc)
    with pytest.raises(RecommendationError):
        CapacityActionRecommendation(
            recommendation_id="x", forecast_evidence=bad_evidence, current_state=rec.current_state,
            cost_book=rec.cost_book, constraints=rec.constraints, policy=rec.policy,
            evaluated_candidates=rec.evaluated_candidates, selected_plan_id=rec.selected_plan_id,
            recommendation_time=rec.recommendation_time, validity_seconds=rec.validity_seconds,
            topology=rec.topology)


# ==================================== Hardening item 2: recommendation advisory fields

@pytest.mark.parametrize("field,value", [
    ("advisory_only", False),
    ("shadow_only", False),
    ("actuation_performed", True),
    ("authorization_performed", True),
    ("effect_verified", True),
    ("authority_class", "AUTHORITATIVE"),
    ("execution_capability", "INFRASTRUCTURE_MUTATION"),
])
def test_recommendation_from_dict_rejects_tampered_advisory_field(field, value):
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d[field] = value
    with pytest.raises(RecommendationError):
        _rebuild(d)


# ==================================== Hardening item 3: surplus abstention fields

def test_abstention_from_dict_rejects_surplus_field():
    d = _abstention_dict()
    d["totally_unexpected"] = 1
    with pytest.raises(RecommendationError):
        RecommendationAbstention.from_dict(d)


# =============================== Canonical-time correction: exact microsecond boundaries

from datetime import timedelta, timezone
from ugence_cloud_scaling_controller.forecasting.series import _as_utc


def _construct(rec, **overrides):
    """Direct CapacityActionRecommendation construction from a valid rec's components."""
    fields = dict(
        recommendation_id=rec.recommendation_id, forecast_evidence=rec.forecast_evidence,
        current_state=rec.current_state, cost_book=rec.cost_book, constraints=rec.constraints,
        policy=rec.policy, evaluated_candidates=rec.evaluated_candidates,
        selected_plan_id=rec.selected_plan_id, recommendation_time=rec.recommendation_time,
        validity_seconds=rec.validity_seconds, topology=rec.topology)
    fields.update(overrides)
    return CapacityActionRecommendation(**fields)


def _evidence_with_forecast_for(rec, new_forecast_for):
    fc = rec.forecast_evidence.forecast
    return dataclasses.replace(rec.forecast_evidence,
                               forecast=dataclasses.replace(fc, forecast_for=new_forecast_for))


# (1) canonical endpoint accepted
def test_canonical_forecast_for_accepted():
    rec = _valid_rec()
    fc = rec.forecast_evidence.forecast
    assert _as_utc(fc.forecast_for) == _as_utc(fc.forecast_cutoff) + timedelta(seconds=fc.horizon.seconds)
    # round-trips cleanly
    assert CapacityActionRecommendation.from_dict(rec.to_canonical_dict()).digest() == rec.digest()


# (2) endpoint + 1 microsecond rejected (from_dict AND direct)
def test_forecast_for_plus_one_microsecond_rejected_from_dict():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["forecast_evidence"]["forecast"]["forecast_for"] += timedelta(microseconds=1)
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_forecast_for_plus_one_microsecond_rejected_direct():
    rec = _valid_rec()
    bad = _evidence_with_forecast_for(rec, rec.forecast_evidence.forecast.forecast_for + timedelta(microseconds=1))
    with pytest.raises(RecommendationError):
        _construct(rec, forecast_evidence=bad)


# (3) endpoint - 1 microsecond rejected (from_dict AND direct)
def test_forecast_for_minus_one_microsecond_rejected_from_dict():
    rec = _valid_rec()
    d = rec.to_canonical_dict()
    d["forecast_evidence"]["forecast"]["forecast_for"] -= timedelta(microseconds=1)
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_forecast_for_minus_one_microsecond_rejected_direct():
    rec = _valid_rec()
    bad = _evidence_with_forecast_for(rec, rec.forecast_evidence.forecast.forecast_for - timedelta(microseconds=1))
    with pytest.raises(RecommendationError):
        _construct(rec, forecast_evidence=bad)


# (4) validity_end == canonical endpoint accepted
def _rec_with_validity(validity_seconds):
    app, db = H.subject("app"), H.subject("db")
    return recommend_capacity_action(
        H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=validity_seconds,
        topology=H.topology(subj=app, dependency=db))


def test_validity_end_equal_to_canonical_endpoint_accepted():
    # cutoff=180, horizon=900 -> forecast_for=1080; rec_time=190 -> validity 890 hits it exactly.
    out = _rec_with_validity(890.0)
    assert isinstance(out, CapacityActionRecommendation)
    fc = out.forecast_evidence.forecast
    assert _as_utc(out.recommendation_time) + timedelta(seconds=out.validity_seconds) == _as_utc(fc.forecast_for)
    assert CapacityActionRecommendation.from_dict(out.to_canonical_dict()).digest() == out.digest()


# (5) validity_end + 1 microsecond rejected (from_dict AND direct)
def test_validity_end_plus_one_microsecond_rejected_from_dict():
    out = _rec_with_validity(890.0)
    d = out.to_canonical_dict()
    d["validity_seconds"] = 890.0 + 1e-6  # rec_time + 890.000001s == forecast_for + 1us
    with pytest.raises(RecommendationError):
        _rebuild(d)


def test_validity_end_plus_one_microsecond_rejected_direct():
    out = _rec_with_validity(890.0)
    with pytest.raises(RecommendationError):
        _construct(out, validity_seconds=890.0 + 1e-6)


# (6) equivalent UTC offsets for the same instant accepted
def test_equivalent_utc_offset_accepted():
    rec = _valid_rec()
    fc = rec.forecast_evidence.forecast
    tz = timezone(timedelta(hours=5))
    bad = dataclasses.replace(rec.forecast_evidence, forecast=dataclasses.replace(
        fc, forecast_cutoff=fc.forecast_cutoff.astimezone(tz),
        forecast_for=fc.forecast_for.astimezone(tz)))
    out = _construct(rec, forecast_evidence=bad)
    assert isinstance(out, CapacityActionRecommendation)


# (7) consistent naive datetimes follow the UTC-normalization policy
def test_consistent_naive_forecast_datetimes_accepted():
    rec = _valid_rec()
    fc = rec.forecast_evidence.forecast
    bad = dataclasses.replace(rec.forecast_evidence, forecast=dataclasses.replace(
        fc, forecast_cutoff=fc.forecast_cutoff.replace(tzinfo=None),
        forecast_for=fc.forecast_for.replace(tzinfo=None)))
    out = _construct(rec, forecast_evidence=bad)
    assert isinstance(out, CapacityActionRecommendation)


# (8) fractional horizon constructs and round-trips
def test_fractional_horizon_round_trip():
    app, db = H.subject("app"), H.subject("db")
    fe = H.build_forecast_evidence(8, subj=app, horizon_seconds=900.5)
    out = recommend_capacity_action(
        fe, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app, dependency=db),
        H.constraints(max_capacity=50), H.policy(), recommendation_time=H.at(190),
        validity_seconds=600.0, topology=H.topology(subj=app, dependency=db))
    assert isinstance(out, CapacityActionRecommendation)
    fc = out.forecast_evidence.forecast
    assert _as_utc(fc.forecast_for) == _as_utc(fc.forecast_cutoff) + timedelta(seconds=900.5)
    assert CapacityActionRecommendation.from_dict(out.to_canonical_dict()).digest() == out.digest()


# (9) direct construction and from_dict reject the SAME noncanonical value
def test_direct_and_from_dict_reject_same_noncanonical_forecast_for():
    rec = _valid_rec()
    off = rec.forecast_evidence.forecast.forecast_for + timedelta(microseconds=1)
    d = rec.to_canonical_dict()
    d["forecast_evidence"]["forecast"]["forecast_for"] = off
    with pytest.raises(RecommendationError):
        _rebuild(d)
    with pytest.raises(RecommendationError):
        _construct(rec, forecast_evidence=_evidence_with_forecast_for(rec, off))


# (10) canonical recommendation + abstention round-trip with stable digests
def test_canonical_records_roundtrip_stable():
    rec = _valid_rec()
    assert CapacityActionRecommendation.from_dict(rec.to_canonical_dict()).digest() == rec.digest()
    d = _abstention_dict()
    ab = RecommendationAbstention.from_dict(d)
    assert RecommendationAbstention.from_dict(ab.to_canonical_dict()).digest() == ab.digest()
