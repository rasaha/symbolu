"""H1 — reconstruction & audit-integrity tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain_audit.events import HiringDomainEventType
from ugence_ai_hiring.errors import CrossTenantHiringAccessError, RequisitionNotFoundError
from ugence_ai_hiring.intake.intake import EvidenceProvenance, IntakeSource
from .h1_helpers import build_env, ctx, open_requisition_with_published_def


def _full_application(env, c):
    open_requisition_with_published_def(env, c, required_evidence_types=("resume",))
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    env.application_service.start_screening(c, "a1")
    env.intake_service.intake_evidence(
        c, application_id="a1", evidence_type="resume", content_hash="h",
        provenance=EvidenceProvenance(source=IntakeSource.CANDIDATE_SUBMISSION, collected_by="r"))
    env.application_service.advance_to_assessment(c, "a1")
    env.application_service.advance_to_review(c, "a1")
    env.application_service.close_application(c, "a1")


def test_reconstruct_application_full_lifecycle():
    env = build_env(); c = ctx()
    _full_application(env, c)
    r = env.reconstruction_service.reconstruct(c, entity_type="application", entity_id="a1")
    assert r.reconstructed
    assert r.hash_chain_valid and r.state_lineage_consistent
    assert r.final_state == "CLOSED"
    assert r.version_count == 5  # RECEIVED..CLOSED
    assert not r.issues


def test_reconstruct_requisition_and_candidate():
    env = build_env(); c = ctx()
    _full_application(env, c)
    rq = env.reconstruction_service.reconstruct(c, entity_type="requisition", entity_id="req1")
    assert rq.reconstructed and rq.final_state == "OPEN"
    cd = env.reconstruction_service.reconstruct(c, entity_type="candidate", entity_id="c1")
    assert cd.reconstructed and cd.final_state == "ACTIVE"


def test_reconstruction_detects_tampered_audit_hash():
    env = build_env(); c = ctx()
    _full_application(env, c)
    # Tamper: replace one event in the store with a copy whose new_state was altered
    # but whose event_hash is left unchanged (as an attacker who can't recompute it).
    chain = list(env.audit_repo._by_entity[("application", "a1")])
    victim = chain[2]
    forged = victim.model_copy(update={"new_state": "TAMPERED"})  # event_hash now stale
    chain[2] = forged
    env.audit_repo._by_entity[("application", "a1")] = chain
    r = env.reconstruction_service.reconstruct(c, entity_type="application", entity_id="a1")
    assert not r.hash_chain_valid
    assert not r.reconstructed
    assert any("event_hash" in i or "chain" in i for i in r.issues)


def test_reconstruction_tenant_isolation():
    env = build_env()
    owner, intruder = ctx(tenant="t1"), ctx(tenant="t2")
    _full_application(env, owner)
    with pytest.raises(CrossTenantHiringAccessError):
        env.reconstruction_service.reconstruct(intruder, entity_type="application", entity_id="a1")


def test_reconstruct_unknown_entity_raises_not_found():
    env = build_env(); c = ctx()
    with pytest.raises(RequisitionNotFoundError):
        env.reconstruction_service.reconstruct(c, entity_type="requisition", entity_id="nope")


def test_audit_chain_links_are_contiguous():
    env = build_env(); c = ctx()
    _full_application(env, c)
    events = env.audit_repo.events_for("application", "a1")
    prev = ""
    for e in events:
        assert e.previous_event_hash == prev
        assert e.hash_is_valid()
        prev = e.event_hash
