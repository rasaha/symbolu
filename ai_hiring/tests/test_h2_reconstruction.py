"""H2 — recommendation reconstruction & audit-integrity tests."""

from __future__ import annotations

import pytest
from governance_providers.contracts import AssertionCoverage

from ai_hiring.errors import CrossTenantHiringAccessError, RecommendationNotFoundError
from ai_hiring.tests.h2_helpers import (
    application_in_assessment,
    build_h2_env,
    evaluator,
    generator,
    humanctx,
    provider,
    sysctx,
)


def _rec(env, c):
    application_in_assessment(env, c)
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    return env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))


def test_reconstruct_recommendation_full_provenance():
    env = build_h2_env(); c = sysctx()
    rec = _rec(env, c)
    r = env.reconstruction_service.reconstruct(c, rec.recommendation_id)
    assert r.reconstructed
    assert r.evidence_refs == ("intk_code_sample", "intk_resume")
    assert r.rubric_version == 1 and r.job_definition_version >= 1
    assert len(r.claims) == 2 and len(r.provider_bindings) == 2
    assert r.provenance_fingerprint  # package fingerprint preserved
    assert r.hash_chain_valid


def test_reconstruction_audit_chain_is_contiguous():
    env = build_h2_env(); c = sysctx()
    rec = _rec(env, c)
    events = env.audit_repo.events_for("recommendation", rec.recommendation_id)
    prev = ""
    for e in events:
        assert e.previous_event_hash == prev and e.hash_is_valid()
        prev = e.event_hash


def test_reconstruction_detects_tampered_event():
    env = build_h2_env(); c = sysctx()
    rec = _rec(env, c)
    key = ("recommendation", rec.recommendation_id)
    chain = list(env.audit_repo._by_entity[key])
    chain[0] = chain[0].model_copy(update={"new_state": "TAMPERED"})  # stale event_hash
    env.audit_repo._by_entity[key] = chain
    r = env.reconstruction_service.reconstruct(c, rec.recommendation_id)
    assert not r.hash_chain_valid and not r.reconstructed


def test_reconstruction_shows_supersession_chain():
    env = build_h2_env(); c = sysctx()
    r1 = _rec(env, c)
    pkg = env.packages.latest_for_application("a1")
    r2 = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)), supersede_existing=True)
    recon1 = env.reconstruction_service.reconstruct(c, r1.recommendation_id)
    assert recon1.superseded_by == r2.recommendation_id
    assert recon1.final_status == "SUPERSEDED"


def test_reconstruction_tenant_isolation():
    env = build_h2_env()
    owner = sysctx(tenant="t1")
    rec = _rec(env, owner)
    with pytest.raises(CrossTenantHiringAccessError):
        env.reconstruction_service.reconstruct(sysctx(tenant="t2"), rec.recommendation_id)


def test_reconstruct_unknown_recommendation():
    env = build_h2_env(); c = sysctx()
    with pytest.raises(RecommendationNotFoundError):
        env.reconstruction_service.reconstruct(c, "missing")
