"""H3 — governance-case reconstruction & cross-linked audit."""

from __future__ import annotations

import pytest

from ai_hiring.errors import CrossTenantHiringAccessError, RecommendationNotFoundError
from ai_hiring.governance.outcomes import HiringDecisionIntent
from ai_hiring.tests.h3_helpers import ai_ctx, build_h3_env, human_ctx, ready_recommendation


def _decided(env):
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    env.governance.record_human_decision(
        human_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.ADVANCE)
    return rec


def test_reconstruct_full_governed_decision():
    env = build_h3_env()
    rec = _decided(env)
    r = env.reconstruction.reconstruct(human_ctx(), rec.recommendation_id)
    assert r.reconstructed
    assert r.hiring_recommendation.recommendation_id == rec.recommendation_id
    assert r.claims and r.provider_bindings           # provider-result persistence
    assert r.decision_case is not None
    assert len(r.kernel_recommendations) == 1 and len(r.decisions) == 1
    assert r.decision_cites_recommendation and r.human_authority_upheld
    assert r.binding_status == "DECIDED"


def test_reconstruction_cross_links_hiring_and_governance_audit():
    env = build_h3_env()
    rec = _decided(env)
    r = env.reconstruction.reconstruct(human_ctx(), rec.recommendation_id)
    assert r.hiring_audit_events            # hiring-owned trail
    assert r.governance_audit_events        # DGM governance trail (by correlation id)
    # both trails share the case correlation id
    corr = env.bindings.for_recommendation(rec.recommendation_id).correlation_id
    assert all(e.correlation_id == corr for e in r.hiring_audit_events if e.correlation_id)


def test_reconstruction_hiring_hash_chain_verifies():
    env = build_h3_env()
    rec = _decided(env)
    r = env.reconstruction.reconstruct(human_ctx(), rec.recommendation_id)
    assert r.hiring_hash_chain_valid
    prev = ""
    for e in r.hiring_audit_events:
        assert e.previous_event_hash == prev and e.hash_is_valid()
        prev = e.event_hash


def test_reconstruction_shows_override():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    env.governance.record_human_decision(
        human_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.REJECT,
        override_notes="override")
    r = env.reconstruction.reconstruct(human_ctx(), rec.recommendation_id)
    assert r.overrides


def test_reconstruction_tenant_isolation():
    env = build_h3_env()
    rec = _decided(env)
    with pytest.raises(CrossTenantHiringAccessError):
        env.reconstruction.reconstruct(human_ctx(tenant="t2", actor="human-t2"), rec.recommendation_id)


def test_reconstruct_unbound_recommendation():
    env = build_h3_env()
    rec = ready_recommendation(env)  # never opened a case
    with pytest.raises(RecommendationNotFoundError):
        env.reconstruction.reconstruct(human_ctx(), rec.recommendation_id)
