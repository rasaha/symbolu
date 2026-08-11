"""Neutral Agent Runtime event adapter — duck-typed, no AR import (spec §5, §11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_risk_authority_execution_assurance import RuntimeEventAdapter
from ugence_risk_authority_execution_assurance.correlation import (
    ExecutionCorrelator,
    GovernedAuthorityContext,
)


@dataclass
class FakeARState:
    """A neutral, duck-typed stand-in for the AR CanonicalExecutionState."""

    instance_id: str = "wf1"
    correlation_id: str = "c1"
    proposal_fingerprint: str = "pf1"
    provider_id: Optional[str] = "cloud"
    idempotency_key: Optional[str] = "idem1"
    attempt: int = 1
    task_id: Optional[str] = "task1"
    execution_reference: Optional[str] = None
    result_digest: Optional[str] = None


def test_derives_attempt_evidence_from_neutral_event():
    ev = RuntimeEventAdapter().to_attempt_evidence(FakeARState())
    assert ev.workflow_instance_id == "wf1"
    assert ev.proposal_fingerprint == "pf1"
    assert ev.attempt == 1
    # attempt_id falls back to idempotency identity when no execution_reference seam.
    assert ev.attempt_id == "idem1#attempt-1"


def test_execution_reference_seam_preferred_when_populated():
    ev = RuntimeEventAdapter().to_attempt_evidence(
        FakeARState(execution_reference="exec-ref-9")
    )
    assert ev.attempt_id == "exec-ref-9"


def test_malformed_attempt_normalized_to_zero():
    ev = RuntimeEventAdapter().to_attempt_evidence(FakeARState(attempt=True))  # bool
    assert ev.attempt == 0
    ev2 = RuntimeEventAdapter().to_attempt_evidence(FakeARState(attempt=-5))
    assert ev2.attempt == 0


def test_none_fields_never_fabricated():
    ev = RuntimeEventAdapter().to_attempt_evidence(
        FakeARState(provider_id=None, idempotency_key=None)
    )
    assert ev.provider_id == ""
    assert ev.idempotency_key == ""


def test_join_mismatch_on_wrong_correlation_or_fingerprint():
    adapter = RuntimeEventAdapter()
    corr = ExecutionCorrelator().mint(
        GovernedAuthorityContext(
            tenant_id="t1", workflow_instance_id="wf1", envelope_id="env",
            authorized_action_digest="pf1", correlation_id="c1",
        ),
        attempt_id="idem1#attempt-1",
    )
    good = adapter.to_attempt_evidence(FakeARState())
    assert adapter.join_mismatches(corr, good) == ()
    bad = adapter.to_attempt_evidence(FakeARState(correlation_id="OTHER"))
    assert "wrong correlation_id" in adapter.join_mismatches(corr, bad)
    bad2 = adapter.to_attempt_evidence(FakeARState(proposal_fingerprint="OTHER"))
    assert "wrong proposal_fingerprint" in adapter.join_mismatches(corr, bad2)
