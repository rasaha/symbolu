"""Shared builders. Every instant is explicit; no test reads a wall clock."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_agent_runtime_governance import CompositionInputs
from ugence_approval_workflow import (
    ApproverKind,
    ApproverRef,
    ReviewDecision,
    SqliteApprovalWorkflowStore,
    StaticApproverEligibility,
)
from ugence_governance_contracts.api import Validity
from ugence_risk_authority_runtime.contracts import (
    GovernanceRestrictions,
    GovernanceVetoResult,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    VetoDisposition,
)

from ugence_governed_review import ApprovalBoundInputSource

TENANT = "tenant-a"
ROLE = "risk-approver"
LABEL = "risk-approver"
REQUESTER = "governed-review"
ENVELOPE_ID = "rae_review_0001"

T0 = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)

APPROVER = ApproverRef(approver_id="approver-1", approver_kind=ApproverKind.HUMAN, role=ROLE,
                       authority_reference="directory://roles/risk-approver")
OTHER_ROLE_APPROVER = ApproverRef(approver_id="approver-9", approver_kind=ApproverKind.HUMAN,
                                  role="auditor")


class Clock:
    """A settable wall clock shared by the runtime (epoch float) and the source (datetime)."""

    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def datetime(self) -> datetime:
        return self.now

    def epoch(self) -> float:
        return self.now.timestamp()

    def advance(self, **kwargs: Any) -> None:
        self.now = self.now + timedelta(**kwargs)


class _Scope:
    purposes = ("review",)
    tools_allow = frozenset({"recorder", "p"})
    tools_deny = frozenset()
    data_allow = frozenset({"d"})
    data_deny = frozenset()
    destinations = frozenset({"dest"})
    jurisdictions = frozenset({"eu"})
    max_autonomy_level = 2
    max_amount_minor_units = 10_000
    required_approvals = frozenset()


class UpstreamSource:
    """A deployment's real source, reduced to the three per-source results.

    ``da`` and ``required_approvals`` are what make a proposal ESCALATE-bound; the
    envelope expiry is one hour past the clock so a granted composition is fresh.
    """

    def __init__(self, *, clock: Clock, da: VetoDisposition = VetoDisposition.HOLD,
                 required_approvals: frozenset = frozenset({LABEL}),
                 ra: RiskAuthorityDisposition = RiskAuthorityDisposition.ALLOW,
                 envelope: Any = None, tier: Any = None, absent: bool = False) -> None:
        self._clock = clock
        self._da = da
        self._labels = required_approvals
        self._ra = ra
        self._envelope = envelope
        self._tier = tier
        self._absent = absent
        self.calls = 0

    def inputs_for(self, proposal: TransitionProposal) -> Optional[CompositionInputs]:
        self.calls += 1
        if self._absent:
            return None
        ra = RiskAuthorityMachineResult(
            disposition=self._ra,
            reason_codes=("RA_ALLOW",) if self._ra is RiskAuthorityDisposition.ALLOW else ("RA_DENY",),
            envelope_id=ENVELOPE_ID, action_digest=proposal.fingerprint[:16], scope=_Scope(),
            expires_at=self._clock.datetime() + timedelta(hours=1), source_version="review",
        )
        return CompositionInputs(
            risk_authority=ra,
            decision_authority=GovernanceVetoResult(
                source="decision_authority", disposition=self._da,
                reason_codes=(f"DA_{self._da.value}",),
                restrictions=GovernanceRestrictions(required_approvals=self._labels,
                                                    max_amount_minor_units=500),
                source_version="review",
            ),
            actiongate=GovernanceVetoResult(source="actiongate", disposition=VetoDisposition.NO_VETO,
                                            reason_codes=("AG_NO_VETO",), source_version="review"),
            action=None, envelope=self._envelope, tier=self._tier,
        )


def proposal(*, instance_id: str = "i1", task_id: str = "t1", arguments: Optional[dict] = None,
             correlation_id: str = "corr-1") -> TransitionProposal:
    return TransitionProposal.build(
        workflow_id="wf", instance_id=instance_id, task_id=task_id, provider_id="p",
        operation="op", arguments=arguments if arguments is not None else {"a": 1},
        idempotency_key=f"{instance_id}:{task_id}", correlation_id=correlation_id,
    )


def sqlite_ledger(tmp_path, *approvers: ApproverRef) -> SqliteApprovalWorkflowStore:
    eligibility = StaticApproverEligibility(approvers or (APPROVER,))
    return SqliteApprovalWorkflowStore(os.path.join(str(tmp_path), "approvals.sqlite3"), eligibility)


def source(ledger, clock: Clock, upstream: Optional[UpstreamSource] = None,
           **kwargs: Any) -> ApprovalBoundInputSource:
    return ApprovalBoundInputSource(
        upstream=upstream or UpstreamSource(clock=clock), ledger=ledger, tenant_id=TENANT,
        required_role=ROLE, clock=clock.datetime, requester_ref=REQUESTER, **kwargs,
    )


def decide(ledger, approval_id: str, *, as_of: datetime, approver: ApproverRef = APPROVER,
           decision: ReviewDecision = ReviewDecision.GRANT):
    """Record a human decision through the ledger's own transitions."""

    return ledger.decide(approval_id, approver=approver, decision=decision, as_of=as_of,
                         justification="reviewed")


def window(issued: datetime, *, hours: int) -> Validity:
    return Validity(issued_at=issued, expires_at=issued + timedelta(hours=hours))
