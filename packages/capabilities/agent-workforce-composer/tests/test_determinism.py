"""Determinism, replay, and digest-sensitivity tests (§24 — Determinism; I5, I6)."""
from __future__ import annotations

from ugence_agent_workforce_composer.eligibility import (
    build_replay_record,
    evaluate_registry_for_role,
    evaluate_workflow_eligibility,
)
from ugence_agent_workforce_composer import fixtures
from ._helpers import NOW, eligibility, enterprise, make_evidence, make_profile, make_role, make_snapshot


def test_replay_byte_equivalent_across_runs():
    a1 = evaluate_workflow_eligibility(*_pipeline())
    a2 = evaluate_workflow_eligibility(*_pipeline())
    assert a1.workflow_fingerprint == a2.workflow_fingerprint
    assert a1.model_dump() == a2.model_dump()


def _pipeline():
    adapt, _ = fixtures.run_demo("procurement")
    snap = fixtures.registry_snapshot()
    return (adapt, snap, fixtures.enterprise_policy(), fixtures.eligibility_policy(),
            fixtures.LOGICAL_TIME)


def test_input_ordering_does_not_change_logical_result():
    role = make_role(required_evidence_classes=("MEASURED",))
    profiles = [make_profile("a", "1.0.0"), make_profile("b", "1.0.0"), make_profile("c", "1.0.0")]
    ev = [make_evidence(p.agent_id, "1.0.0", "evidence_extraction", "MEASURED") for p in profiles]
    s1 = make_snapshot(profiles, ev)
    s2 = make_snapshot(list(reversed(profiles)), list(reversed(ev)))
    r1 = evaluate_registry_for_role(role, s1, enterprise(), eligibility(), NOW)
    r2 = evaluate_registry_for_role(role, s2, enterprise(), eligibility(), NOW)
    assert r1.report_fingerprint == r2.report_fingerprint


def test_snapshot_change_alters_result_fingerprint():
    role = make_role(required_evidence_classes=("MEASURED",))
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED")]
    base = evaluate_registry_for_role(role, make_snapshot([p], ev), enterprise(), eligibility(), NOW)
    p2 = make_profile("a", "1.0.0", security_classification=1)
    changed = evaluate_registry_for_role(role, make_snapshot([p2], ev), enterprise(), eligibility(), NOW)
    assert base.report_fingerprint != changed.report_fingerprint


def test_policy_digest_change_alters_result_fingerprint():
    role = make_role(required_evidence_classes=("MEASURED",))
    p = make_profile("a", "1.0.0")
    ev = [make_evidence("a", "1.0.0", "evidence_extraction", "MEASURED")]
    snap = make_snapshot([p], ev)
    r1 = evaluate_registry_for_role(role, snap, enterprise(minimum_security_classification=2),
                                    eligibility(), NOW)
    r2 = evaluate_registry_for_role(role, snap, enterprise(minimum_security_classification=4),
                                    eligibility(), NOW)
    assert r1.results[0].result_fingerprint != r2.results[0].result_fingerprint


def test_replay_record_is_deterministic():
    adapt, snap, ent, elig, t = _pipeline()
    role = adapt.role_requirements[0]
    rep = evaluate_registry_for_role(role, snap, ent, elig, t)
    rec1 = build_replay_record(role, rep, ent, elig, t)
    rec2 = build_replay_record(role, rep, ent, elig, t)
    assert rec1.replay_fingerprint == rec2.replay_fingerprint
    assert rec1.snapshot_digest == snap.snapshot_digest
    assert rec1.role_fingerprint == role.role_fingerprint
