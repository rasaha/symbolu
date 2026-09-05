"""The workflow port both adapters implement.

A *port* is a provider-neutral seam. A composition root injects one adapter here
and one :class:`~ugence_approval_workflow.eligibility.ApproverEligibilityPort`; the
package depends on nothing else. Every instant is a caller input.

None of these methods approves anything. ``decide`` **records** the decision an
eligible human or committee already made, having refused it when the structural
rules do not hold.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_governance_contracts.api import Validity

from .consumption import ConsumeOutcome
from .eligibility import ApproverRef
from .records import ApprovalEvent, ApprovalRecord
from .states import ApprovalState, ReviewDecision
from .subject import ApprovalSubject

__all__ = ["ApprovalWorkflowPort"]


@runtime_checkable
class ApprovalWorkflowPort(Protocol):
    """Queue, state machine, bounded exception path and once-only consumption."""

    def request_approval(self, subject: ApprovalSubject, *, requested_by: str,
                         required_role: str, validity: Validity, as_of: datetime,
                         request_ordinal: int = 1, supersedes: str = "",
                         justification: str = "", is_fixture: bool = False) -> ApprovalRecord: ...

    def present_for_decision(self, approval_id: str, *, as_of: datetime) -> ApprovalRecord: ...

    def decide(self, approval_id: str, *, approver: ApproverRef, decision: ReviewDecision,
               as_of: datetime, justification: str = "",
               accepted_finding_ids: tuple[str, ...] = (),
               signature_reference: str = "",
               authentication_reference: str = "") -> ApprovalRecord: ...

    def request_exception(self, approval_id: str, *, requested_by: str, justification: str,
                          exception_validity: Validity, as_of: datetime) -> ApprovalRecord: ...

    def decide_exception(self, approval_id: str, *, approver: ApproverRef, granted: bool,
                         as_of: datetime, justification: str = "",
                         signature_reference: str = "") -> ApprovalRecord: ...

    def withdraw(self, approval_id: str, *, by: str, as_of: datetime,
                 justification: str = "") -> ApprovalRecord: ...

    def consume(self, approval_id: str, *, consumer_ref: str, subject_digest: str,
                as_of: datetime) -> ConsumeOutcome: ...

    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]: ...

    def state_at(self, approval_id: str, *, as_of: datetime) -> ApprovalState: ...

    def list_open(self, *, tenant_id: str, required_role: str = "",
                  as_of: datetime) -> tuple[ApprovalRecord, ...]: ...

    def approval_events(self, approval_id: str) -> tuple[ApprovalEvent, ...]: ...
