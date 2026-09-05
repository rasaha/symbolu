"""The ``ApproverEligibilityPort`` adapter for the approval workflow.

The **port is owned by the consumer**
(``packages/integration/approval-workflow/src/ugence_approval_workflow/eligibility.py:95-106``);
this package satisfies it and never imports it, so the dependency edge runs one way
and the approval package's own boundary test keeps refusing the reverse.

Satisfying it without importing it is possible because the seam is structural: the
port is a ``runtime_checkable`` Protocol, and the values crossing it are read by
attribute. :class:`DirectoryApproverRef` therefore carries exactly
``approver_id``, ``approver_kind``, ``role`` and ``authority_reference``, with
``approver_kind`` a ``str`` enum whose member values match the consumer's
``ApproverKind`` — so ``ApproverKind.HUMAN``, ``PrincipalKind.HUMAN`` and ``"HUMAN"``
compare and hash equal, and a ref this adapter returns can be handed straight to
``decide()``. ``tests/integration`` proves that against the real package.

What this adapter does **not** do: authenticate, resolve a session, hold a
credential, or decide that a principal is who they claim. It reports role grants that
are valid at the caller's instant, and the consumer applies its own rules — including
its refusal of ``AI``, ``SERVICE`` and ``DELEGATED_POLICY`` kinds, which no answer
here can widen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ._canon import optional_text, require_nonempty, require_tzaware
from .directory import AuthorityDirectoryPort
from .errors import ContractViolation
from .grants import RoleGrant
from .principals import PrincipalKind

__all__ = ["DirectoryApproverRef", "EligibilityAnswer", "DirectoryApproverEligibility",
           "projection_of"]


@dataclass(frozen=True)
class DirectoryApproverRef:
    """The projection of a role grant the consumer's port expects.

    Structurally an ``ApproverRef``: same four attributes, same enum *values*.
    """

    approver_id: str
    approver_kind: PrincipalKind
    role: str
    authority_reference: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "approver_id",
                           require_nonempty(self.approver_id, "DirectoryApproverRef.approver_id"))
        object.__setattr__(self, "role",
                           require_nonempty(self.role, "DirectoryApproverRef.role"))
        object.__setattr__(self, "authority_reference",
                           optional_text(self.authority_reference,
                                         "DirectoryApproverRef.authority_reference"))
        if not isinstance(self.approver_kind, PrincipalKind):
            raise ContractViolation(
                "DirectoryApproverRef.approver_kind must be a PrincipalKind member")


@dataclass(frozen=True)
class EligibilityAnswer:
    """A typed answer, never a bare boolean. ``reasons`` is empty exactly when eligible.

    Structurally the consumer's ``EligibilityDecision``, and validated the same way.
    """

    eligible: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.eligible and self.reasons:
            raise ContractViolation("an eligible answer carries no reasons")
        if not self.eligible and not self.reasons:
            raise ContractViolation("an ineligible answer must state its reasons")


def projection_of(grant: RoleGrant) -> DirectoryApproverRef:
    """Project a grant onto the consumer's approver shape. No secret crosses the seam."""

    return DirectoryApproverRef(
        approver_id=grant.principal_id, approver_kind=grant.principal.principal_kind,
        role=grant.role, authority_reference=grant.authority_reference)


class DirectoryApproverEligibility:
    """Answers the approval workflow's eligibility questions from role grants."""

    def __init__(self, directory: AuthorityDirectoryPort, *,
                 scope_prefix: str = "approval") -> None:
        if not isinstance(directory, AuthorityDirectoryPort):
            raise ContractViolation(
                "an AuthorityDirectoryPort is required at construction")
        self._directory = directory
        self._scope_prefix = require_nonempty(scope_prefix, "scope_prefix")

    # ------------------------------------------------------------------ #
    def scope_for(self, subject_kind: str, subject_digest: str) -> str:
        """The scope a grant must cover to be eligible for this subject.

        A composition root that scopes its roles differently subclasses nothing and
        supplies its own adapter; this is one deterministic convention, not a rule.
        """

        return (f"{self._scope_prefix}/{require_nonempty(subject_kind, 'subject_kind')}"
                f"/{require_nonempty(subject_digest, 'subject_digest')}")

    # ------------------------------------------------------------------ #
    # ApproverEligibilityPort
    # ------------------------------------------------------------------ #
    def eligible_approvers(self, *, tenant_id: str, subject_kind: str, subject_digest: str,
                           required_role: str, as_of: datetime) -> tuple[DirectoryApproverRef, ...]:
        require_tzaware(as_of, "eligible_approvers.as_of")
        role = optional_text(required_role, "required_role")
        scope = self.scope_for(subject_kind, subject_digest)
        holders = self._directory.holders_of(tenant_id=tenant_id, role=role, scope=scope,
                                             as_of=as_of) if role else ()
        return tuple(projection_of(g) for g in holders)

    def is_eligible(self, *, tenant_id: str, approver, required_role: str,
                    scope: str, as_of: datetime) -> EligibilityAnswer:
        require_tzaware(as_of, "is_eligible.as_of")
        role = optional_text(required_role, "required_role")
        subject_kind, _, subject_digest = str(scope).partition(":")
        try:
            wanted = self.scope_for(subject_kind, subject_digest)
        except ContractViolation:
            return EligibilityAnswer(False, ("the presented scope is not a directory scope",))

        held = self._directory.grants_for(tenant_id=tenant_id,
                                          principal_id=getattr(approver, "approver_id", ""),
                                          as_of=as_of)
        if not held:
            return EligibilityAnswer(False, ("the principal holds no valid grant in this tenant",))
        matching = [g for g in held if (not role or g.role == role) and g.covers(wanted)]
        if not matching:
            return EligibilityAnswer(
                False, (f"no valid grant of role '{role or 'any'}' covers '{wanted}'",))

        presented_kind = getattr(approver, "approver_kind", None)
        if presented_kind is not None and not any(
                g.principal.principal_kind == presented_kind for g in matching):
            return EligibilityAnswer(
                False, ("the presented approver kind differs from the directory record",))
        presented_role = getattr(approver, "role", "")
        if presented_role and not any(g.role == presented_role for g in matching):
            return EligibilityAnswer(
                False, ("the presented role differs from the directory record",))
        return EligibilityAnswer(True)

    # ------------------------------------------------------------------ #
    def committee_for(self, *, tenant_id: str, committee_id: str, required_role: str,
                      subject_kind: str, subject_digest: str, as_of: datetime):
        """The committee's quorum and currently-valid members, for a caller that needs
        them. This adapter never counts votes and never reports a quorum as met."""

        return self._directory.committee_report(
            tenant_id=tenant_id, committee_id=committee_id, role=required_role,
            scope=self.scope_for(subject_kind, subject_digest), as_of=as_of)
