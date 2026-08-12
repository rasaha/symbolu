"""Phase-3 typed-abstention tests — the bulk of the deny/rejection matrix.

Every branch that lacks sufficient or consistent authoritative evidence must return a TYPED
:class:`RecommendationAbstention` (never a fabricated recommendation, never a generic error).
"""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    CostBasis,
    CostBook,
    CostEvidence,
    DependencyEdge,
    DependencyKind,
    DependencyTopology,
    Money,
    OperatingConstraints,
    RecommendationAbstention,
    RecommendationAbstentionReason as RR,
    recommend_capacity_action,
)
from ugence_cloud_scaling_controller.planning.pipeline import PipelineError
import ph_helpers as H


def _run(fe, st, cb, con, pol=None, **kw):
    kw.setdefault("recommendation_time", H.at(190.0))
    kw.setdefault("validity_seconds", 600.0)
    return recommend_capacity_action(fe, st, cb, con, pol or H.policy(), **kw)


def _assert_abstains(out, reason):
    assert isinstance(out, RecommendationAbstention), f"expected abstention, got {type(out).__name__}"
    assert out.reason is reason, f"expected {reason}, got {out.reason}"


# --- forecast evidence ---------------------------------------------------------------

def test_missing_forecast():
    app = H.subject()
    out = _run(None, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints())
    _assert_abstains(out, RR.MISSING_FORECAST)


def test_forecast_abstained():
    app = H.subject()
    out = _run(H.build_abstained_forecast(subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints())
    _assert_abstains(out, RR.FORECAST_ABSTAINED)


def test_unsupported_forecast_target():
    app = H.subject()
    out = _run(H.build_cpu_forecast_evidence(subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints())
    _assert_abstains(out, RR.UNSUPPORTED_FORECAST_TARGET)


def test_insufficient_forecast_confidence():
    app = H.subject()
    pol = H.policy(min_forecast_confidence=0.5)  # point-only forecast has confidence 0.0
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(), pol)
    _assert_abstains(out, RR.INSUFFICIENT_FORECAST_CONFIDENCE)


# --- canonical state -----------------------------------------------------------------

def test_missing_canonical_state():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), None, H.cost_book(subj=app), H.constraints())
    _assert_abstains(out, RR.MISSING_CANONICAL_STATE)


def test_missing_current_capacity():
    from ugence_cloud_scaling_controller.canonical import CanonicalCapacityState
    app = H.subject()
    st = CanonicalCapacityState(subject=app, observed_at=H.at(180))  # no capacity block
    out = _run(H.build_forecast_evidence(8, subj=app), st, H.cost_book(subj=app), H.constraints())
    _assert_abstains(out, RR.MISSING_CURRENT_CAPACITY)


def test_subject_scope_mismatch_forecast_vs_state():
    app = H.subject("app")
    other = H.subject("other")
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=other),
               H.cost_book(subj=other), H.constraints())
    _assert_abstains(out, RR.SUBJECT_SCOPE_MISMATCH)


def test_subject_scope_mismatch_cost_book():
    app = H.subject("app")
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=H.subject("other")), H.constraints())
    _assert_abstains(out, RR.SUBJECT_SCOPE_MISMATCH)


# --- topology ------------------------------------------------------------------------

def test_missing_topology_when_required():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(), require_topology=True)
    _assert_abstains(out, RR.MISSING_TOPOLOGY)


def test_stale_topology():
    app, db = H.subject("app"), H.subject("db")
    topo = H.topology(subj=app, dependency=db, as_of=H.at(0))  # old
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, dependency=db), H.constraints(), topology=topo,
               max_topology_age_seconds=60.0)
    _assert_abstains(out, RR.STALE_TOPOLOGY)


def test_dependency_cycle():
    app, db = H.subject("app"), H.subject("db")
    topo = DependencyTopology(subject=app, as_of=H.at(120), edges=(
        DependencyEdge(app, db, DependencyKind.INFORMATIONAL),
        DependencyEdge(db, app, DependencyKind.INFORMATIONAL),
    ))
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), H.constraints(), topology=topo)
    _assert_abstains(out, RR.DEPENDENCY_CYCLE)


def test_missing_dependency_capacity():
    app, db = H.subject("app"), H.subject("db")
    topo = DependencyTopology(subject=app, as_of=H.at(120), edges=(
        DependencyEdge(app, db, DependencyKind.CAPACITY_BOUND),))  # no capacity evidence
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, dependency=db), H.constraints(), topology=topo)
    _assert_abstains(out, RR.MISSING_DEPENDENCY_CAPACITY)


# --- cost ----------------------------------------------------------------------------

def test_missing_cost_evidence():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               None, H.constraints())
    _assert_abstains(out, RR.MISSING_COST_EVIDENCE)


def test_incompatible_cost_basis():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, app_basis=CostBasis.PER_CONNECTION_HOUR), H.constraints())
    _assert_abstains(out, RR.INCOMPATIBLE_COST_EVIDENCE)


def test_stale_cost_evidence():
    app = H.subject()
    cb = H.cost_book(subj=app, effective_from=H.at(-100), effective_until=H.at(100))  # ends before 190
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               cb, H.constraints())
    _assert_abstains(out, RR.STALE_COST_EVIDENCE)


def test_currency_mismatch():
    app, db = H.subject("app"), H.subject("db")
    cb = CostBook(subject=app, entries=(
        CostEvidence(app, Money(1000, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(-3600), H.at(36000)),
        CostEvidence(db, Money(50, "EUR"), CostBasis.PER_CONNECTION_HOUR, H.at(-3600), H.at(36000)),
    ))
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               cb, H.constraints())
    _assert_abstains(out, RR.CURRENCY_MISMATCH)


# --- constraints ---------------------------------------------------------------------

def test_missing_constraints():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), None)
    _assert_abstains(out, RR.MISSING_CONSTRAINTS)


def test_quota_conflict():
    app = H.subject()
    con = OperatingConstraints(min_capacity=5, max_capacity=10, regional_quota=3)  # quota < min
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app), con)
    _assert_abstains(out, RR.QUOTA_CONFLICT)


def test_no_feasible_action():
    # current below min, forecast small so no scale-up is generated -> all candidates infeasible.
    app = H.subject()
    out = _run(H.build_forecast_evidence(2, subj=app), H.replicas_state(H.at(180), 2, subj=app),
               H.cost_book(subj=app), H.constraints(min_capacity=5, max_capacity=50))
    _assert_abstains(out, RR.NO_FEASIBLE_ACTION)


# --- temporal ------------------------------------------------------------------------

def test_future_forecast_cutoff():
    app = H.subject()
    # Valid forecast (cutoff 250, near its series) but the recommendation is made at t=200,
    # BEFORE the cutoff -> the forecast is "future" relative to the recommendation.
    fe = H.build_forecast_evidence(8, subj=app, cutoff=H.at(250))
    out = _run(fe, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints(),
               recommendation_time=H.at(200))
    _assert_abstains(out, RR.FUTURE_DATA_LEAKAGE)


def test_future_state_observation():
    app = H.subject()
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(9999), 6, subj=app),
               H.cost_book(subj=app), H.constraints())
    _assert_abstains(out, RR.FUTURE_DATA_LEAKAGE)


def test_expired_forecast_horizon_elapsed():
    app = H.subject()
    fe = H.build_forecast_evidence(8, subj=app, cutoff=H.at(100), horizon_seconds=60.0)  # for=160
    out = _run(fe, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app),
               H.constraints(), recommendation_time=H.at(300))  # 300 > forecast_for 160
    _assert_abstains(out, RR.EXPIRED_FORECAST)


def test_expired_forecast_validity_window():
    app = H.subject()
    fe = H.build_forecast_evidence(8, subj=app, cutoff=H.at(100), horizon_seconds=3600.0)
    con = H.constraints(forecast_validity_seconds=30.0)  # age = 190-100 = 90 > 30
    out = _run(fe, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), con)
    _assert_abstains(out, RR.EXPIRED_FORECAST)


def test_recommendation_window_beyond_horizon():
    app = H.subject()
    fe = H.build_forecast_evidence(8, subj=app, cutoff=H.at(100), horizon_seconds=200.0)  # for=300
    out = _run(fe, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints(),
               recommendation_time=H.at(190), validity_seconds=10000.0)  # window ends far past 300
    _assert_abstains(out, RR.CONTRADICTORY_EVIDENCE)


def test_future_topology():
    app, db = H.subject("app"), H.subject("db")
    topo = H.topology(subj=app, dependency=db, as_of=H.at(9999))  # future as_of
    out = _run(H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
               H.cost_book(subj=app, dependency=db), H.constraints(), topology=topo)
    _assert_abstains(out, RR.FUTURE_DATA_LEAKAGE)


# --- misuse (programming error, NOT abstention) --------------------------------------

def test_both_state_and_forecast_none_raises():
    with pytest.raises(PipelineError):
        _run(None, None, None, None)


def test_abstention_round_trip():
    app = H.subject()
    out = _run(None, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints())
    out2 = RecommendationAbstention.from_dict(out.to_canonical_dict())
    assert out2.digest() == out.digest()
    assert out2.reason is out.reason
