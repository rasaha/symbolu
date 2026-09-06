"""Contracts for governed diff-driven review (PWC-P3A).

Every object here is a **standalone artifact**. Nothing in this module is added to
:class:`~ugence_policy_workflow_compiler.models.policy_pack.PolicyPack`, to
:class:`~ugence_policy_workflow_compiler.models.approvals.HumanApprovalRecord`, or
to the compiled release's logical payload — a review artifact stored inside the pack
would change the very digest the review is bound to. Review objects sit beside the
pack exactly as ``PolicyPackDiff`` does, which is what keeps ``policy_pack.v1``,
``workflow_ir.v1`` and ``workflow_ir.v2`` bytes unchanged.

Ratified rulings this module implements:

* **P3A-1** ``REVIEW_ENFORCEMENT = BLOCKING`` — an unsatisfied requirement refuses
  compilation. No minor-change exemption, no approval carry-forward, and no
  defaulted reviewer when the pack declares no covering approval path.
* **P3A-2** ``REVIEWER_IDENTITY = OPAQUE_REFERENCE`` —
  :attr:`ReviewDisposition.reviewer_authority_reference` is an uninterpreted binding
  reference. This package neither imports nor resolves an authority directory.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import Field

from ..models.approvals import ApprovalDecision
from ..models.common import CompilerModel

#: The ratified enforcement posture (P3A-1). A requirement that is not satisfied is
#: a refusal, never a warning. Changing this is a ratification, not a setting.
REVIEW_ENFORCEMENT = "BLOCKING"

#: The ratified reviewer-identity posture (P3A-2). The authority reference is
#: carried verbatim and never resolved.
REVIEWER_IDENTITY = "OPAQUE_REFERENCE"


class ReviewCode(str, Enum):
    """Typed, fail-closed refusal codes. Every one is a refusal, never a warning."""

    #: An approval-sensitive change exists and the pack declares no path covering it.
    NO_APPROVAL_PATH_FOR_CHANGE = "NO_APPROVAL_PATH_FOR_CHANGE"
    #: A required (non-optional) step carries no approving disposition.
    REVIEW_REQUIREMENT_UNSATISFIED = "REVIEW_REQUIREMENT_UNSATISFIED"
    #: Dispositions do not follow the pack's declared step order.
    REVIEW_STEP_OUT_OF_ORDER = "REVIEW_STEP_OUT_OF_ORDER"
    #: A segregation pair was satisfied by a single identity.
    SEGREGATION_OF_DUTIES_VIOLATED = "SEGREGATION_OF_DUTIES_VIOLATED"
    #: A disposition binds a digest other than the requirement's new pack digest.
    DISPOSITION_DIGEST_MISMATCH = "DISPOSITION_DIGEST_MISMATCH"
    #: A disposition was authored by the compiler process itself.
    SELF_REVIEW = "SELF_REVIEW"
    #: The ledger addresses a different requirement than the one supplied.
    LEDGER_REQUIREMENT_MISMATCH = "LEDGER_REQUIREMENT_MISMATCH"
    #: A disposition names a step the requirement does not declare.
    UNKNOWN_REVIEW_STEP = "UNKNOWN_REVIEW_STEP"
    #: The requirement does not describe the pack being compiled.
    REQUIREMENT_PACK_MISMATCH = "REQUIREMENT_PACK_MISMATCH"


class ReviewStepRequirement(CompilerModel):
    """One ordered step a reviewer must satisfy, carried from the pack's own
    ``ApprovalStep`` declaration. Nothing here is invented by the compiler."""

    step_id: str = Field(..., min_length=1)
    order: int = Field(..., ge=1)
    authority_requirement_id: str = Field(..., min_length=1)
    role_label: str = ""
    optional: bool = False


class ReviewRequirement(CompilerModel):
    """What a structurally meaningful change obliges, derived from the diff and the
    pack's declared approval path.

    ``review_required`` is ``False`` when the diff shows no approval-sensitive
    change — the artifact still exists so the decision is recorded and auditable
    rather than implied by absence.
    """

    requirement_id: str = Field(..., min_length=1)
    policy_pack_id: str = Field(..., min_length=1)
    old_pack_digest: str = ""
    new_pack_digest: str = Field(..., min_length=1)
    review_required: bool = False
    #: Object ids whose change forced re-review, sorted.
    triggering_object_ids: Tuple[str, ...] = ()
    #: The classified change types behind those objects, sorted and de-duplicated.
    triggering_change_types: Tuple[str, ...] = ()
    #: The declared path that must be re-satisfied. Empty when none covers the change.
    required_approval_path_id: str = ""
    required_steps: Tuple[ReviewStepRequirement, ...] = ()
    #: Segregation-of-duties pairs carried from the declared path.
    segregation_pairs: Tuple[Tuple[str, str], ...] = ()
    #: Refusal codes already established at derivation time (never warnings).
    unresolved_codes: Tuple[str, ...] = ()

    @property
    def is_blocking(self) -> bool:
        """True when this requirement can refuse a compilation (P3A-1)."""
        return self.review_required or bool(self.unresolved_codes)


class ReviewDisposition(CompilerModel):
    """One reviewer's action on one required step, bound to the changed pack."""

    disposition_id: str = Field(..., min_length=1)
    requirement_id: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    reviewer_role: str = Field(..., min_length=1)
    #: P3A-2: an uninterpreted binding reference. Never resolved by this package.
    reviewer_authority_reference: str = ""
    decision: ApprovalDecision
    #: The digest of the pack actually reviewed. Must equal the requirement's
    #: ``new_pack_digest`` — this is what makes re-review a re-binding.
    policy_pack_digest: str = Field(..., min_length=1)
    decided_at: str = ""
    justification: str = ""


class ReviewLedger(CompilerModel):
    """The ordered dispositions recorded against one requirement.

    The ledger is the evidence that a review happened **against the changed pack**,
    rather than an earlier approval happening to match.
    """

    ledger_id: str = Field(..., min_length=1)
    requirement_id: str = Field(..., min_length=1)
    dispositions: Tuple[ReviewDisposition, ...] = ()


class ReviewCheck(CompilerModel):
    """The outcome of checking a ledger against a requirement."""

    ok: bool
    codes: Tuple[str, ...] = ()
    reasons: Tuple[str, ...] = ()

    @property
    def rejected(self) -> bool:
        return not self.ok


__all__ = [
    "REVIEW_ENFORCEMENT",
    "REVIEWER_IDENTITY",
    "ReviewCode",
    "ReviewStepRequirement",
    "ReviewRequirement",
    "ReviewDisposition",
    "ReviewLedger",
    "ReviewCheck",
]
