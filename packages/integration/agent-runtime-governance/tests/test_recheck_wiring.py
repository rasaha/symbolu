"""The last-mile recheck, wired to a REAL revocable authority.

ADR §8 row 6 established the negative case: with ``authority_recheck`` unset, a
revocation landing between CLEAR and the effect goes unnoticed and the provider is
invoked. These tests close the loop for GAS-3 — the hook's CLEAR, plus the recheck this
package wires, blocks a real revocation and a real epoch advance at the commit point.

Nothing is mocked. The envelope is a genuine Ed25519-signed
``RiskAuthorizationEnvelope`` built through Risk Authority's own public API by the RA-6
scenario builder, and the revocation is written through the authenticated lifecycle
writer. The failures are Risk Authority's, produced by Risk Authority.
"""
from __future__ import annotations

import pytest

import ra6_scenario as C
from risk_authority.services.authority_status import StalenessPolicy
from ugence_agent_runtime.governance.decisions import (
    CLEAR_REJECTED_AUTHORITY_STALE,
    validate_clearance,
)
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition

import _fakes as F
from ugence_agent_runtime_governance import (
    GovernedExecutionHook,
    build_authority_recheck,
    hook_envelope_resolver,
)


def _wire(harness, hook):
    """The recheck this package builds, over the harness' real authority state."""
    return build_authority_recheck(
        hook=hook,
        reader=harness.cache,
        policy=StalenessPolicy.fail_closed_defaults(),
        key_ring=harness.key_ring,
        clock=lambda: harness.now,
        # Refresh the cache at recheck time, so a revocation that landed after the
        # initial CLEAR is actually observed. Without this the recheck can re-verify
        # against a snapshot as stale as the clearance it is checking.
        sync=lambda: harness.cache.sync(),
    )


def _cleared(harness):
    """A hook that CLEARs, bound to the harness' real signed envelope."""
    hook = GovernedExecutionHook(
        source=F.StaticSource(
            F.inputs(envelope=harness.envelope, tier=harness.residual_risk)
        )
    )
    proposal = F.proposal()
    evaluation = hook.evaluate(proposal, 0.0)
    assert evaluation.disposition is GovernanceDisposition.CLEAR
    return hook, proposal, evaluation


def test_the_resolver_finds_the_envelope_the_clear_rested_on():
    harness = C.build()
    hook, proposal, evaluation = _cleared(harness)

    context = hook_envelope_resolver(hook)(evaluation, proposal)
    assert context is not None
    assert context.envelope is harness.envelope, (
        "the recheck must re-verify the SAME envelope the CLEAR rested on"
    )
    assert context.expected_tenant == harness.envelope.tenant_id


def test_a_clean_authority_passes_the_last_mile():
    harness = C.build()
    hook, proposal, evaluation = _cleared(harness)
    recheck = _wire(harness, hook)

    permitted, reasons = validate_clearance(
        evaluation, proposal, 0.0, authority_recheck=recheck
    )
    assert permitted, f"an unrevoked authority must pass; refused for {reasons}"


def test_revocation_between_clear_and_effect_is_caught():
    """The case ADR §8 row 6 proved goes unnoticed without a configured recheck."""
    harness = C.build()
    hook, proposal, evaluation = _cleared(harness)
    recheck = _wire(harness, hook)

    assert validate_clearance(evaluation, proposal, 0.0, authority_recheck=recheck)[0]

    harness.writer.revoke_envelope(
        principal=harness.admin(),
        tenant_id=C.TENANT,
        envelope_id=harness.envelope.envelope_id,
        reason="revoked mid-flight",
        correlation_id="gas3",
    )

    permitted, reasons = validate_clearance(
        evaluation, proposal, 0.0, authority_recheck=recheck
    )
    assert not permitted, "a revoked envelope must not reach the provider"
    assert reasons[0] == CLEAR_REJECTED_AUTHORITY_STALE
    assert any("revoked" in r for r in reasons), reasons


def test_epoch_advance_between_clear_and_effect_is_caught():
    harness = C.build()
    hook, proposal, evaluation = _cleared(harness)
    recheck = _wire(harness, hook)

    assert validate_clearance(evaluation, proposal, 0.0, authority_recheck=recheck)[0]

    harness.writer.advance_epoch(
        principal=harness.admin(),
        tenant_id=C.TENANT,
        change_id="c-gas3",
        reason="rotation",
        correlation_id="gas3",
    )

    permitted, reasons = validate_clearance(
        evaluation, proposal, 0.0, authority_recheck=recheck
    )
    assert not permitted, "a stale authority epoch must not reach the provider"
    assert any("epoch" in r for r in reasons), reasons


def test_an_uncleared_proposal_has_nothing_for_the_recheck_to_guard():
    """A proposal the hook never cleared resolves to ``None`` and the recheck passes
    through — correct, because the refusal already happened upstream and there is no
    provider call in flight to guard."""
    harness = C.build()
    hook = GovernedExecutionHook(
        source=F.StaticSource(F.inputs(envelope=harness.envelope))
    )
    never_evaluated = F.proposal(task_id="never")

    assert hook.envelope_for(never_evaluated) is None
    assert hook_envelope_resolver(hook)(None, never_evaluated) is None

    recheck = _wire(harness, hook)
    ok, reasons = recheck(None, never_evaluated, 0.0)
    assert ok and reasons == ()


def test_a_refused_proposal_records_no_envelope():
    """A denial must not leave a recheck target behind."""
    from ugence_risk_authority_runtime.contracts import VetoDisposition

    harness = C.build()
    hook = GovernedExecutionHook(
        source=F.StaticSource(
            F.inputs(da=VetoDisposition.DENY, envelope=harness.envelope)
        )
    )
    proposal = F.proposal()
    evaluation = hook.evaluate(proposal, 0.0)

    assert evaluation.disposition is GovernanceDisposition.BLOCK
    assert hook.envelope_for(proposal) is None
