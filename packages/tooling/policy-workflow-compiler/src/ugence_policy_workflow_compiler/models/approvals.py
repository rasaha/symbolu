"""Human approval records.

A :class:`HumanApprovalRecord` captures a reviewer's decision over a specific
policy-pack digest, including which provenance gaps and warnings were explicitly
accepted. A compiler process must never approve its own output, and reviewer
authority is never fabricated. Example approvals are offline fixtures, clearly
labeled as such.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import Field

from .common import CompilerModel, ObjectType, PolicyObject


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"


class HumanApprovalRecord(PolicyObject):
    """A human reviewer's approval decision over a specific pack digest."""

    object_type: ObjectType = ObjectType.HUMAN_APPROVAL_RECORD
    approval_id: str = Field(..., min_length=1)
    policy_pack_id: str = Field(..., min_length=1)
    #: The exact structural digest of the pack that was reviewed. Approval binds
    #: to this digest; recompiling a different pack invalidates the approval.
    policy_pack_digest: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    reviewer_role: str = Field(..., min_length=1)
    #: A non-secret reference to the reviewer's authority (directory handle).
    reviewer_authority_reference: str = ""
    decision: ApprovalDecision
    approved_at: str = ""  # ISO timestamp; recorded metadata, not policy logic
    #: Provenance-gap object ids the reviewer explicitly reviewed and accepted.
    reviewed_gap_ids: Tuple[str, ...] = ()
    #: Warning diagnostic codes/ids the reviewer explicitly accepted.
    accepted_warning_ids: Tuple[str, ...] = ()
    justification: str = ""
    #: A non-secret reference to a detached signature, when present.
    signature_reference: str = ""
    #: True when this record is a labeled offline example fixture (not a real
    #: authority). Example packs set this True.
    is_fixture: bool = False

    @property
    def is_approval(self) -> bool:
        return self.decision is ApprovalDecision.APPROVED
