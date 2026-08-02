"""Reference providers pass the shared conformance kits (by kind)."""
from __future__ import annotations

from ugence_governance_provider_framework.conformance import (
    run_action_provider_conformance, run_assertion_provider_conformance,
    run_execution_provider_conformance)
from ugence_governance_provider_framework.contracts import (
    ActionGovernanceOutcome, AssertionCoverage, ExecutionBusinessOutcome)
from ugence_governance_provider_framework.reference import (
    DeterministicActionGovernanceProvider, DeterministicAssertionProvider,
    DeterministicExecutionProvider)


def test_assertion_conformance():
    rep = run_assertion_provider_conformance(lambda: DeterministicAssertionProvider())
    assert rep.passed, rep.failures


def test_action_conformance():
    rep = run_action_provider_conformance(lambda: DeterministicActionGovernanceProvider())
    assert rep.passed, rep.failures


def test_execution_conformance():
    rep = run_execution_provider_conformance(lambda: DeterministicExecutionProvider())
    assert rep.passed, rep.failures


def test_reference_action_paths():
    p = DeterministicActionGovernanceProvider(denied=frozenset({"D"}), constrained=frozenset({"C"}))
    p.initialize()
    from ugence_governance_provider_framework.contracts import ActionGovernanceRequest
    assert p.authorize(ActionGovernanceRequest("OK")).outcome is ActionGovernanceOutcome.AUTHORIZED
    assert p.authorize(ActionGovernanceRequest("D")).outcome is ActionGovernanceOutcome.DENIED
    assert p.authorize(ActionGovernanceRequest("C")).outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS


def test_reference_assertion_paths():
    from ugence_governance_provider_framework.contracts import AssertionGovernanceRequest
    for cov in AssertionCoverage:
        p = DeterministicAssertionProvider(coverage=cov); p.initialize()
        r = p.evaluate(AssertionGovernanceRequest("x", evidence_refs=("e",)))
        assert r.coverage is cov


def test_reference_execution_paths():
    from ugence_governance_provider_framework.contracts import ExecutionDispatchRequest
    p = DeterministicExecutionProvider(
        transport_failing=frozenset({"F"}), timing_out=frozenset({"T"}),
        outcomes={"R": ExecutionBusinessOutcome.REJECTED}); p.initialize()
    assert not p.dispatch(ExecutionDispatchRequest("F")).accepted
    assert p.dispatch(ExecutionDispatchRequest("T")).timed_out
    ok = p.dispatch(ExecutionDispatchRequest("R"))
    assert p.observe(external_request_id=ok.external_request_id).business_outcome is ExecutionBusinessOutcome.REJECTED
    assert p.cancel(external_request_id=ok.external_request_id)
