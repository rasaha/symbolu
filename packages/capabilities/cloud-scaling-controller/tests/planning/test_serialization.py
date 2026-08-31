"""Phase-3 serialization + determinism tests (round-trip, stable digests, ordering)."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.canonical.serialization import CanonicalizationError, canonical_json
from ugence_cloud_scaling_controller.planning import (
    CapacityActionRecommendation,
    recommend_capacity_action,
)
import ph_helpers as H


def _rec(current=6, predicted=8):
    app, db = H.subject("app"), H.subject("db")
    return recommend_capacity_action(
        H.build_forecast_evidence(predicted, subj=app), H.replicas_state(H.at(180), current, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=600.0, topology=H.topology(subj=app, dependency=db))


def test_recommendation_round_trip_preserves_digest():
    rec = _rec()
    rt = CapacityActionRecommendation.from_dict(rec.to_canonical_dict())
    assert rt.digest() == rec.digest()


def test_recommendation_canonical_json_is_deterministic():
    rec = _rec()
    j1 = canonical_json(rec.to_canonical_dict())
    j2 = canonical_json(rec.to_canonical_dict())
    assert j1 == j2


def test_digest_included_matches_method():
    rec = _rec()
    d = rec.to_canonical_dict(include_digest=True)
    assert d["evidence_digest"] == rec.digest()


def test_digest_stable_across_two_builds():
    assert _rec().digest() == _rec().digest()


def test_no_change_vs_scale_have_distinct_digests():
    assert _rec(current=6, predicted=6).digest() != _rec(current=6, predicted=8).digest()


def test_recommendation_advisory_fields_present_in_dict():
    d = _rec().to_canonical_dict()
    assert d["advisory_only"] is True
    assert d["shadow_only"] is True
    assert d["actuation_performed"] is False
    assert d["authorization_performed"] is False
    assert d["effect_verified"] is False
    assert d["authority_class"] == "ADVISORY"
    assert d["execution_capability"] == "NONE"


def test_canonicalization_rejects_non_finite():
    with pytest.raises(CanonicalizationError):
        canonical_json({"x": float("nan")})
