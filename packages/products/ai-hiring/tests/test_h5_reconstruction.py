"""H5 — audit completeness + reconstruction integrity across scenarios."""
from __future__ import annotations

from ugence_ai_hiring.validation import CaseSpec, build_validation_env, run_lifecycle, score_case


def test_audit_completeness_full_for_executed_case():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="ac1"))
    s = score_case(env, r)
    assert s.passed and not s.critical_failures
    for item in ("source_evidence", "human_authority", "authorization_record", "execution_attempt",
                 "receipt", "reconciliation", "hash_chain_verified"):
        assert s.items[item], item


def test_reconstruction_full_chain_intact():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="ac2"))
    rc = env.action_reconstruction.reconstruct(env.ai(), r.action_proposal_id)
    assert rc.reconstructed
    assert rc.recommendation is not None and rc.claims and rc.provider_claim_bindings
    assert rc.human_decision is not None and rc.authorizations and rc.attempts and rc.reconciliations
    assert rc.links_intact and rc.tenant_scope_consistent


def test_reconstruction_detects_broken_link():
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="ac3"))
    # break the attempt→authorization link by injecting an attempt with a bogus authorization_id
    attempts = env.attempts.for_proposal(r.action_proposal_id)
    bogus = attempts[0].model_copy(update={"attempt_id": "bogus", "authorization_id": "nope"})
    env.attempts.add(bogus)
    rc = env.action_reconstruction.reconstruct(env.ai(), r.action_proposal_id)
    assert not rc.links_intact and not rc.reconstructed


def test_audit_completeness_never_hides_critical_failure():
    # a case whose execution failed (malformed) must not pass completeness as "executed"
    env = build_validation_env()
    r = run_lifecycle(env, CaseSpec(case_id="ac4", exec_flags={"malformed": True}))
    # not executed → no receipt; completeness for a non-executed action does not falsely pass
    assert r.proposal_status == "EXECUTION_FAILED" and not r.execution_status
