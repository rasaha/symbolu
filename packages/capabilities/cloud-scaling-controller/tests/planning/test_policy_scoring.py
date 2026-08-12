"""Phase-3 policy + score-breakdown tests (matrix G: scoring integrity)."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_controller.planning import (
    FEATURE_NAMES,
    PolicyError,
    RecommendationPolicy,
    ScoreBreakdown,
)
from ugence_cloud_scaling_controller.planning.policy import SCORE_BREAKDOWN_SCHEMA_VERSION


def _pol():
    return RecommendationPolicy()


def _valid_breakdown(policy):
    feats = {f: 0.5 for f in FEATURE_NAMES}
    contribs = {f: policy.sign_for(f) * policy.weight_for(f) * feats[f] for f in FEATURE_NAMES}
    total = sum(contribs.values())
    return ScoreBreakdown(features=feats, contributions=contribs, total_score=total,
                          policy_id=policy.policy_id, policy_digest=policy.digest())


def test_policy_negative_weight_rejected():
    with pytest.raises(PolicyError):
        RecommendationPolicy(w_coverage=-1.0)


def test_policy_non_finite_weight_rejected():
    with pytest.raises(PolicyError):
        RecommendationPolicy(w_cost=float("inf"))


def test_policy_round_trip():
    p = RecommendationPolicy(policy_id="p2", w_coverage=5.0, coverage_floor=0.9)
    p2 = RecommendationPolicy.from_dict(p.to_canonical_dict())
    assert p2.digest() == p.digest()


def test_policy_digest_changes_with_weight():
    a = RecommendationPolicy(w_cost=1.0)
    b = RecommendationPolicy(w_cost=2.0)
    assert a.digest() != b.digest()


def test_score_breakdown_valid_recomputes():
    p = _pol()
    sb = _valid_breakdown(p)
    # total equals sum of contributions
    assert abs(sb.total_score - sum(sb.contributions.values())) < 1e-9


def test_score_breakdown_forged_total_rejected():
    p = _pol()
    feats = {f: 0.5 for f in FEATURE_NAMES}
    contribs = {f: p.sign_for(f) * p.weight_for(f) * feats[f] for f in FEATURE_NAMES}
    with pytest.raises(PolicyError):
        ScoreBreakdown(features=feats, contributions=contribs, total_score=999.0,
                       policy_id=p.policy_id, policy_digest=p.digest())


def test_score_breakdown_unknown_feature_rejected():
    p = _pol()
    feats = {f: 0.5 for f in FEATURE_NAMES}
    feats["bogus"] = 1.0
    contribs = {f: 0.0 for f in FEATURE_NAMES}
    with pytest.raises(PolicyError):
        ScoreBreakdown(features=feats, contributions=contribs, total_score=0.0,
                       policy_id=p.policy_id, policy_digest=p.digest())


def test_score_breakdown_non_finite_feature_rejected():
    p = _pol()
    feats = {f: 0.5 for f in FEATURE_NAMES}
    feats["coverage"] = float("nan")
    contribs = {f: 0.0 for f in FEATURE_NAMES}
    with pytest.raises(PolicyError):
        ScoreBreakdown(features=feats, contributions=contribs, total_score=0.0,
                       policy_id=p.policy_id, policy_digest=p.digest())


def test_score_breakdown_round_trip():
    p = _pol()
    sb = _valid_breakdown(p)
    sb2 = ScoreBreakdown.from_dict(sb.to_canonical_dict())
    assert sb2.digest() == sb.digest()
    assert sb2.total_score == sb.total_score
