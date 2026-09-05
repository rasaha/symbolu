"""The adversarial suite: HOLD, ESCALATE and BLOCK can never widen to CLEAR.

Two layers, because a projection can be wrong in two different ways:

* **Composition-driven** — real ``RiskAuthorityMachineResult`` / ``GovernanceVetoResult``
  objects through the REAL ``RiskAuthorityCompositionEngine``, so what is asserted is the
  ratified composition's own behaviour, not a stand-in for it.
* **Projection-driven** — hostile decision objects the real engine could never produce,
  fed straight to the projection to prove it refuses look-alikes, liars and wreckage.

Throughout, the property under test is one-directional: nothing that is not an
unambiguous GRANT may come back CLEAR, and a CLEAR must be bound to the exact proposal.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest

import _fakes as F
from ugence_agent_runtime.governance.decisions import (
    RuntimeDirective,
    directive_for,
    permits_execution,
    validate_clearance,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceHook,
)
from ugence_risk_authority_runtime.contracts import (
    FinalDisposition,
    RiskAuthorityDisposition,
    VetoDisposition,
)

from ugence_agent_runtime_governance import (
    REASON_COMPOSITION_FAILED,
    REASON_MALFORMED_INPUTS,
    REASON_NO_AUTHORIZATION_REFERENCE,
    REASON_NOT_A_FINAL_DISPOSITION,
    REASON_NOT_AUTHORITY_BOUND,
    REASON_NOT_EXECUTABLE,
    REASON_SOURCE_UNAVAILABLE,
    GovernedExecutionHook,
    project_disposition,
)

pytestmark = [pytest.mark.adversarial]

RESTRICTIVE = (
    GovernanceDisposition.HOLD,
    GovernanceDisposition.BLOCK,
    GovernanceDisposition.ESCALATE,
)


def _hook(source, engine=None) -> GovernedExecutionHook:
    return GovernedExecutionHook(source=source, engine=engine)


# --------------------------------------------------------------------------- #
# structural conformance
# --------------------------------------------------------------------------- #
def test_the_hook_satisfies_the_runtime_protocol():
    hook = _hook(F.StaticSource(F.inputs()))
    assert isinstance(hook, GovernanceHook)


# --------------------------------------------------------------------------- #
# layer 1 — through the REAL composition engine
# --------------------------------------------------------------------------- #
def test_all_clear_composes_to_clear():
    """The one path that may CLEAR: RA ALLOW, no veto, no emptied scope."""
    hook = _hook(F.StaticSource(F.inputs()))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.CLEAR
    assert permits_execution(result)
    assert result.authorization_reference == F.ENVELOPE_ID, (
        "the binding reference must be Risk Authority's own envelope id"
    )


@pytest.mark.parametrize(
    "ra_disposition",
    [RiskAuthorityDisposition.DENY, RiskAuthorityDisposition.ERROR],
)
def test_risk_authority_deny_or_error_never_clears(ra_disposition):
    """RA DENY is absorbing and RA ERROR has no authority basis. Neither may clear."""
    hook = _hook(F.StaticSource(F.inputs(ra=F.ra_result(ra_disposition))))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition in RESTRICTIVE
    assert not permits_execution(result)
    assert result.authorization_reference is None, (
        "a refusal must not ship a binding reference — that would be a clearance "
        "shaped like a denial"
    )


@pytest.mark.parametrize(
    "da,ag",
    [
        (d, a)
        for d, a in itertools.product(VetoDisposition, VetoDisposition)
        if not (d is VetoDisposition.NO_VETO and a is VetoDisposition.NO_VETO)
    ],
)
def test_no_veto_combination_ever_clears(da, ag):
    """Every combination of governance inputs except the all-clear one is restrictive.

    Exhaustive over the veto vocabulary rather than sampled: a single combination that
    slipped through to CLEAR is the whole failure mode this package exists to prevent.
    """
    hook = _hook(F.StaticSource(F.inputs(da=da, ag=ag)))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition in RESTRICTIVE, (
        f"da={da.value} ag={ag.value} produced {result.disposition}"
    )
    assert directive_for(result) is not RuntimeDirective.CONTINUE


def test_governance_hold_maps_to_a_non_executing_disposition():
    hook = _hook(F.StaticSource(F.inputs(da=VetoDisposition.HOLD)))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.HOLD
    assert directive_for(result) is RuntimeDirective.WAIT
    assert result.required_resolution == "GOVERNANCE_HOLD_RELEASE"


def test_a_hold_requiring_approval_escalates_rather_than_waiting():
    """Both park the workflow; ESCALATE says a human is the thing being waited on."""
    from ugence_risk_authority_runtime.contracts import GovernanceRestrictions

    hook = _hook(
        F.StaticSource(
            F.inputs(
                da=VetoDisposition.HOLD,
                da_restrictions=GovernanceRestrictions(
                    required_approvals=frozenset({"cfo"})
                ),
            )
        )
    )
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.ESCALATE
    assert directive_for(result) is RuntimeDirective.PAUSE
    assert result.required_resolution == "EXTERNAL_APPROVAL"
    assert not permits_execution(result)


def test_restrictions_that_empty_the_scope_deny():
    """Governance may only subtract; subtracting everything leaves nothing to execute."""
    from ugence_risk_authority_runtime.contracts import GovernanceRestrictions

    hook = _hook(
        F.StaticSource(
            F.inputs(
                da_restrictions=GovernanceRestrictions(
                    allow_intersections={"tools_allow": frozenset()}
                )
            )
        )
    )
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.BLOCK
    assert not permits_execution(result)


# --------------------------------------------------------------------------- #
# layer 2 — hostile inputs the real engine could never produce
# --------------------------------------------------------------------------- #
def test_a_string_lookalike_for_grant_is_refused():
    """``FinalDisposition`` is a str enum, so ``"GRANT" == FinalDisposition.GRANT`` and
    both hash alike. Equality and dict lookup are unsafe; ``isinstance`` is not."""
    assert "GRANT" == FinalDisposition.GRANT      # the hazard, stated
    assert hash("GRANT") == hash(FinalDisposition.GRANT)

    disposition, reasons = project_disposition(
        F.SpoofedDecision(final_disposition="GRANT", executable=True)
    )
    assert disposition is GovernanceDisposition.BLOCK
    assert REASON_NOT_A_FINAL_DISPOSITION in reasons


def test_a_decision_claiming_executable_while_denying_is_refused():
    """The disposition drives the mapping; a self-reported boolean never does."""
    disposition, _ = project_disposition(
        F.SpoofedDecision(final_disposition=FinalDisposition.DENY, executable=True)
    )
    assert disposition is GovernanceDisposition.BLOCK


def test_grant_without_executable_is_refused():
    disposition, reasons = project_disposition(
        F.SpoofedDecision(final_disposition=FinalDisposition.GRANT, executable=False)
    )
    assert disposition is GovernanceDisposition.BLOCK
    assert REASON_NOT_EXECUTABLE in reasons


@pytest.mark.parametrize("bogus", [None, 0, 1, True, "", "CLEAR", object(), ...])
def test_absent_or_nonsense_dispositions_are_refused(bogus):
    disposition, _ = project_disposition(
        F.SpoofedDecision(final_disposition=bogus, executable=True)
    )
    assert disposition is GovernanceDisposition.BLOCK


def test_a_none_decision_is_refused():
    disposition, reasons = project_disposition(None)
    assert disposition is GovernanceDisposition.BLOCK
    assert REASON_NOT_A_FINAL_DISPOSITION in reasons


def test_an_uninspectable_decision_is_refused():
    """Every attribute access raises. Wreckage is not permission."""
    disposition, _ = project_disposition(F.ExplodingDecision())
    assert disposition is GovernanceDisposition.BLOCK


def test_projection_is_total_over_the_final_disposition_vocabulary():
    """Every member maps somewhere, and only GRANT maps to CLEAR."""
    for member in FinalDisposition:
        decision = F.SpoofedDecision(
            final_disposition=member,
            executable=(member is FinalDisposition.GRANT),
            effective_constraints=F.constraints(),
        )
        disposition, _ = project_disposition(decision)
        assert isinstance(disposition, GovernanceDisposition)
        if member is FinalDisposition.GRANT:
            assert disposition is GovernanceDisposition.CLEAR
        else:
            assert disposition in RESTRICTIVE, f"{member} widened to {disposition}"


# --------------------------------------------------------------------------- #
# failure of the machinery itself
# --------------------------------------------------------------------------- #
def test_an_unavailable_input_source_blocks_and_does_not_raise():
    """A hook that threw would make "no answer" indistinguishable from "not asked"."""
    hook = _hook(F.RaisingSource())
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.BLOCK
    assert REASON_SOURCE_UNAVAILABLE in result.reason_codes


def test_a_failing_composition_engine_blocks():
    hook = _hook(F.StaticSource(F.inputs()), engine=F.ExplodingEngine())
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.BLOCK
    assert REASON_COMPOSITION_FAILED in result.reason_codes


def test_a_none_from_the_source_is_not_permission():
    hook = _hook(F.StaticSource(None))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.BLOCK
    assert REASON_NOT_AUTHORITY_BOUND in result.reason_codes


@pytest.mark.parametrize("junk", [{}, "inputs", 42, object()])
def test_malformed_inputs_are_refused(junk):
    hook = _hook(F.StaticSource(junk))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.BLOCK
    assert REASON_MALFORMED_INPUTS in result.reason_codes


def test_a_grant_without_an_envelope_id_is_refused_rather_than_given_a_minted_one():
    """There is nothing to bind the clearance to, and inventing an identifier would make
    an unbindable permission look bindable."""
    hook = _hook(F.StaticSource(F.inputs(ra=F.ra_result(envelope_id=""))))
    result = hook.evaluate(F.proposal(), 1000.0)

    assert result.disposition is GovernanceDisposition.BLOCK
    assert REASON_NO_AUTHORIZATION_REFERENCE in result.reason_codes
    assert result.binding_reference() is None


# --------------------------------------------------------------------------- #
# binding: a CLEAR must survive the runtime's own validation
# --------------------------------------------------------------------------- #
def test_a_clear_passes_the_runtime_clearance_validation():
    """The real gate: ``validate_clearance`` is what stands between a CLEAR and a
    provider call, so the hook's output is asserted against it directly."""
    hook = _hook(F.StaticSource(F.inputs()))
    p = F.proposal()
    result = hook.evaluate(p, 1000.0)

    permitted, reasons = validate_clearance(result, p, 1000.0)
    assert permitted, f"the hook's CLEAR must be actionable; refused for {reasons}"


def test_a_clear_is_bound_to_the_exact_proposal_and_not_another():
    """A clearance for one proposal must not authorize a different one."""
    hook = _hook(F.StaticSource(F.inputs()))
    cleared = F.proposal(task_id="t1")
    other = F.proposal(task_id="t2")
    result = hook.evaluate(cleared, 1000.0)

    assert result.proposal_fingerprint == cleared.fingerprint
    assert cleared.fingerprint != other.fingerprint

    permitted, reasons = validate_clearance(result, other, 1000.0)
    assert not permitted, "a clearance must not transfer to a different proposal"


def test_a_clear_carries_the_proposals_correlation_reference():
    hook = _hook(F.StaticSource(F.inputs()))
    p = F.proposal(correlation_id="corr-xyz")
    result = hook.evaluate(p, 1000.0)

    assert result.correlation_reference == "corr-xyz"
    permitted, _ = validate_clearance(result, p, 1000.0)
    assert permitted


def test_a_mismatched_correlation_fails_the_runtime_gate():
    """Belt and braces: the runtime refuses a correlation mismatch even if a hook were
    to produce one."""
    hook = _hook(F.StaticSource(F.inputs()))
    p = F.proposal(correlation_id="corr-a")
    result = hook.evaluate(p, 1000.0)
    other = F.proposal(correlation_id="corr-b")

    permitted, _ = validate_clearance(result, other, 1000.0)
    assert not permitted


def test_expiry_is_projected_onto_the_runtime_wall_clock_base():
    """``valid_until`` must be epoch seconds, comparable to the runtime's injected clock."""
    expires = datetime.now(timezone.utc) + timedelta(seconds=60)
    hook = _hook(
        F.StaticSource(F.inputs(ra=F.ra_result(expires_in_s=60.0)))
    )
    p = F.proposal()
    result = hook.evaluate(p, 1000.0)

    assert result.valid_until is not None
    assert abs(result.valid_until - expires.timestamp()) < 5.0, (
        "valid_until must be epoch seconds on the same base as wall_clock()"
    )

    permitted, _ = validate_clearance(result, p, result.valid_until - 1.0)
    assert permitted, "valid strictly before expiry"

    permitted, _ = validate_clearance(result, p, result.valid_until)
    assert not permitted, "expiry is inclusive: at now == valid_until it is expired"


def test_a_naive_expiry_is_read_as_utc_not_local_time():
    """Guessing the host zone could move an expiry hours in the permissive direction."""
    from ugence_agent_runtime_governance.hook import _epoch_seconds

    naive = datetime(2030, 1, 1, 12, 0, 0)
    aware = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert _epoch_seconds(naive) == _epoch_seconds(aware) == aware.timestamp()


def test_an_unconvertible_expiry_yields_no_claim_rather_than_a_fabricated_one():
    from ugence_agent_runtime_governance.hook import _epoch_seconds

    for bogus in (None, "soon", 12345, object()):
        assert _epoch_seconds(bogus) is None


# --------------------------------------------------------------------------- #
# the hook mints nothing
# --------------------------------------------------------------------------- #
def test_the_hook_never_produces_a_reference_the_authority_did_not():
    """Every reference on every outcome is either absent or Risk Authority's own id."""
    cases = [
        F.inputs(),
        F.inputs(da=VetoDisposition.DENY),
        F.inputs(da=VetoDisposition.HOLD),
        F.inputs(ag=VetoDisposition.ERROR),
        F.inputs(ra=F.ra_result(RiskAuthorityDisposition.DENY)),
    ]
    for case in cases:
        hook = _hook(F.StaticSource(case))
        result = hook.evaluate(F.proposal(), 1000.0)
        for ref in (
            result.evaluation_reference,
            result.authorization_reference,
            result.clearance_reference,
        ):
            assert ref in (None, F.ENVELOPE_ID), f"minted reference {ref!r}"


def test_the_hook_records_an_envelope_only_for_a_cleared_proposal():
    """The recheck resolver keys off this; recording on a refusal would give the recheck
    something to guard that was never permitted."""
    sentinel = object()
    hook = _hook(F.StaticSource(F.inputs(envelope=sentinel)))
    cleared = F.proposal(task_id="ok")
    hook.evaluate(cleared, 1000.0)
    assert hook.envelope_for(cleared) == (sentinel, None)

    denied_hook = _hook(
        F.StaticSource(F.inputs(da=VetoDisposition.DENY, envelope=sentinel))
    )
    denied = F.proposal(task_id="no")
    denied_hook.evaluate(denied, 1000.0)
    assert denied_hook.envelope_for(denied) is None


# --------------------------------------------------------------------------- #
# the clearance record is bounded, and dropping a record never widens
# --------------------------------------------------------------------------- #
def test_the_clearance_record_refuses_at_capacity_rather_than_evicting():
    """With the record full of live clearances a new CLEAR is refused; nothing in
    flight is dropped to make room."""
    from ugence_agent_runtime_governance import REASON_RECORD_CAPACITY

    hook = GovernedExecutionHook(source=F.StaticSource(F.inputs()), max_records=2)
    first, second, third = (F.proposal(task_id=t) for t in ("a", "b", "c"))
    assert hook.evaluate(first, 1000.0).disposition is GovernanceDisposition.CLEAR
    assert hook.evaluate(second, 1000.0).disposition is GovernanceDisposition.CLEAR
    assert hook.record_count == 2

    refused = hook.evaluate(third, 1000.0)
    assert refused.disposition is GovernanceDisposition.BLOCK
    assert REASON_RECORD_CAPACITY in refused.reason_codes
    assert refused.authorization_reference is None
    assert hook.record_count == 2, "refusal must not evict a live record"
    assert hook.envelope_for(first) is not None and hook.envelope_for(second) is not None

    # Re-evaluating an already-recorded proposal is not a new record.
    assert hook.evaluate(first, 1000.0).disposition is GovernanceDisposition.CLEAR
    assert hook.record_count == 2


def test_a_consumed_record_is_dropped_at_the_next_sweep_and_frees_capacity():
    hook = GovernedExecutionHook(source=F.StaticSource(F.inputs()), max_records=1)
    first, second = F.proposal(task_id="a"), F.proposal(task_id="b")
    assert hook.evaluate(first, 1000.0).disposition is GovernanceDisposition.CLEAR
    assert hook.evaluate(second, 1000.0).disposition is GovernanceDisposition.BLOCK

    assert hook.consume_envelope(first) is not None
    # Still readable until the next evaluation: a retry within the same quantum
    # re-verifies the same envelope rather than nothing.
    assert hook.envelope_for(first) is not None

    assert hook.evaluate(second, 1001.0).disposition is GovernanceDisposition.CLEAR
    assert hook.envelope_for(first) is None
    assert hook.record_count == 1


def test_an_expired_clearance_record_is_swept():
    hook = GovernedExecutionHook(source=F.StaticSource(F.inputs()))
    proposal = F.proposal(task_id="a")
    now = datetime.now(timezone.utc).timestamp()
    evaluation = hook.evaluate(proposal, now)
    assert evaluation.disposition is GovernanceDisposition.CLEAR
    assert evaluation.valid_until is not None
    assert hook.envelope_for(proposal) is not None

    hook.evaluate(F.proposal(task_id="b"), evaluation.valid_until + 1.0)
    assert hook.envelope_for(proposal) is None, "an expired record is not kept"


def test_the_bound_holds_under_many_clearances():
    """N distinct proposals through a hook with a small cap never leave more than the
    cap in the record, whatever mix of consumption and expiry happens between them."""
    cap = 8
    hook = GovernedExecutionHook(source=F.StaticSource(F.inputs()), max_records=cap)
    for i in range(200):
        p = F.proposal(task_id=f"t{i}")
        hook.evaluate(p, 1000.0 + i)
        assert hook.record_count <= cap
        if i % 3 == 0:
            hook.consume_envelope(p)
    assert hook.record_count <= cap


def test_the_resolver_fails_closed_for_a_clear_whose_record_is_gone():
    """A None from the resolver is a pass-through for the recheck. A CLEAR whose record
    was dropped must therefore never resolve to None: it raises, and the runtime turns a
    raising recheck into a refusal."""
    from ugence_agent_runtime.governance.decisions import AUTHORITY_RECHECK_ERROR

    from ugence_agent_runtime_governance import hook_envelope_resolver
    from ugence_agent_runtime_governance.recheck import ClearanceRecordMissing

    hook = GovernedExecutionHook(source=F.StaticSource(F.inputs(envelope=object())))
    resolver = hook_envelope_resolver(hook)
    proposal = F.proposal(task_id="a")
    evaluation = hook.evaluate(proposal, 1000.0)
    assert evaluation.disposition is GovernanceDisposition.CLEAR

    assert resolver(evaluation, proposal) is not None  # consumes
    assert resolver(evaluation, proposal) is not None  # a retry before any sweep
    hook.evaluate(F.proposal(task_id="b"), 1001.0)  # sweeps the consumed record

    with pytest.raises(ClearanceRecordMissing):
        resolver(evaluation, proposal)

    def recheck(ev, pr, now):
        resolver(ev, pr)
        return True, ()

    permitted, reasons = validate_clearance(
        evaluation, proposal, 1001.0, authority_recheck=recheck
    )
    assert not permitted
    assert AUTHORITY_RECHECK_ERROR in reasons

    # Never cleared, and no CLEAR evaluation in hand: still a pass-through.
    assert resolver(None, F.proposal(task_id="never")) is None
