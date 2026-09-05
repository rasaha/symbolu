"""The assurance-finding declaration — the only thing this package holds.

An :class:`AssuranceFindingDeclaration` says *this tenant declared that this
exercise found this, about this exact AI system, and the evidence is this
reference, for this window*. It says nothing else, and it can prove nothing the
binding, the reference and the label inside it cannot.

**Nothing here is ours.** The record binds an ``AssessedSystemBinding``, an
``EvidenceReference`` and an ``AssuranceFindingLabel``, all three **re-exported
from governance-contracts** rather than parallel spellings — the direction that
package fixes itself: engines bind the same identity "rather than minting a
parallel one. Consumers re-export it; they never redefine it"
(``packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:17-18``).

**The evidence reference is the sole evidence identity (AE-2).** The declaration
carries the existing ``EvidenceReference`` whole and mints no competing reference:
no second evidence id, no copied provenance field, no parallel digest. Anything
that wants the evidence — TAP citing it, or a composition root building a Risk
Authority ``ControlEvidenceRecord`` from it (AE-4) — reads the same reference, so
both routes name one thing. Neither route is built here.

**Two agreements are enforced, not assumed.** The evidence reference's tenant
must equal the declaration's tenant, and its ``subject_id`` must equal the
binding's ``subject_id``: a finding about one subject bound to another system's
identity is refused at construction, never reconciled either way.

**The label is what was found, uninterpreted (AE-3).** It is not a
``VerificationStatus`` and implies none: whether the evidence was ever checked is
a separate statement this package does not make.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    AssuranceFindingLabel,
    EvidenceReference,
    SystemBindingAuthenticityStatus,
    Validity,
    ValidityStatus,
)

from ._canon import (
    domain_digest,
    from_iso,
    iso,
    optional_text,
    require_nonempty,
    require_tzaware,
)
from .errors import ContractViolation, DeclarationSupersessionError

__all__ = [
    "AssuranceFindingDeclaration", "DECLARATION_ID_PREFIX", "declaration_id_for",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
]

DECLARATION_ID_PREFIX = "afd_"


def validity_to_dict(validity: Validity) -> dict:
    return {"issued_at": iso(validity.issued_at, "Validity.issued_at"),
            "expires_at": iso(validity.expires_at, "Validity.expires_at") if validity.expires_at else "",
            "stale_after": iso(validity.stale_after, "Validity.stale_after") if validity.stale_after else ""}


def validity_from_dict(d: Optional[dict]) -> Optional[Validity]:
    if not d:
        return None
    return Validity(issued_at=from_iso(d["issued_at"]),
                    expires_at=from_iso(d["expires_at"]) if d.get("expires_at") else None,
                    stale_after=from_iso(d["stale_after"]) if d.get("stale_after") else None)


def _evidence_identity(evidence: EvidenceReference) -> dict:
    """The reference's own identity, read through: its id and its content digest."""

    return {"evidence_id": evidence.evidence_id, "content_digest": evidence.content_digest}


def declaration_id_for(binding: AssessedSystemBinding, evidence: EvidenceReference,
                       finding: AssuranceFindingLabel, exercise_ref: str,
                       validity: Validity) -> str:
    """Deterministic declaration id: no UUID, no clock.

    Derived from the binding's own canonical digest, the evidence reference's own
    identity, the label's digest, the exercise reference and the window, so two
    loads of the same declaration are the same declaration, and a different system,
    different evidence, a different finding or a different exercise can never share
    an id.
    """

    if not isinstance(binding, AssessedSystemBinding):
        raise ContractViolation("declaration_id_for.binding must be an AssessedSystemBinding")
    if not isinstance(evidence, EvidenceReference):
        raise ContractViolation("declaration_id_for.evidence must be an EvidenceReference")
    if not isinstance(finding, AssuranceFindingLabel):
        raise ContractViolation("declaration_id_for.finding must be an AssuranceFindingLabel")
    if not isinstance(validity, Validity):
        raise ContractViolation("declaration_id_for.validity must be a governance-contracts Validity")
    return DECLARATION_ID_PREFIX + domain_digest("declaration_id", {
        "binding": binding.canonical_digest(),
        "evidence": _evidence_identity(evidence),
        "finding": finding.canonical_digest(),
        "exercise_ref": require_nonempty(exercise_ref, "exercise_ref"),
        "validity": validity_to_dict(validity),
    })[:32]


@dataclass(frozen=True)
class AssuranceFindingDeclaration:
    """One declared finding, about one exact AI system, for one bounded window."""

    declaration_id: str
    #: The declaring tenant. Must agree with both the binding's and the evidence
    #: reference's tenant; a mismatch is refused, never resolved either way.
    tenant_id: str
    #: Exactly one canonical binding. Never a registry registration.
    binding: AssessedSystemBinding
    #: Exactly one existing evidence reference — the finding's **sole** evidence
    #: identity (AE-2). Carried whole; nothing is copied out of it.
    evidence: EvidenceReference
    #: What the exercise found, as the declarer called it. **Uninterpreted** (AE-3).
    finding: AssuranceFindingLabel
    #: An opaque, non-secret reference to the exercise that produced the finding,
    #: in the caller's own spelling. Nothing here can run it.
    exercise_ref: str
    validity: Validity
    #: The declaration this one replaces. A changed declaration is made afresh;
    #: the prior record is never edited.
    supersedes: str = ""
    declared_by: str = ""
    correlation_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("declaration_id", "tenant_id", "exercise_ref"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name),
                                                f"AssuranceFindingDeclaration.{name}"))
        for name in ("supersedes", "declared_by", "correlation_id", "notes"):
            object.__setattr__(self, name,
                               optional_text(getattr(self, name),
                                             f"AssuranceFindingDeclaration.{name}"))
        if not isinstance(self.binding, AssessedSystemBinding):
            raise ContractViolation(
                "AssuranceFindingDeclaration.binding must be a governance-contracts "
                "AssessedSystemBinding; this package mints no system identity of its own")
        if not isinstance(self.evidence, EvidenceReference):
            raise ContractViolation(
                "AssuranceFindingDeclaration.evidence must be a governance-contracts "
                "EvidenceReference; this package mints no evidence identity of its own")
        if not isinstance(self.finding, AssuranceFindingLabel):
            raise ContractViolation(
                "AssuranceFindingDeclaration.finding must be a governance-contracts "
                "AssuranceFindingLabel; this package mints no vocabulary of its own")
        if not isinstance(self.validity, Validity):
            raise ContractViolation(
                "AssuranceFindingDeclaration.validity must be a governance-contracts Validity")
        if self.tenant_id != self.binding.tenant_id:
            raise ContractViolation(
                f"AssuranceFindingDeclaration.tenant_id {self.tenant_id!r} does not match "
                f"the binding's tenant {self.binding.tenant_id!r}; a declaration never "
                "crosses tenants")
        if self.evidence.tenant_id != self.tenant_id:
            raise ContractViolation(
                f"AssuranceFindingDeclaration.evidence names tenant "
                f"{self.evidence.tenant_id!r}, not the declaring tenant {self.tenant_id!r}; "
                "a declaration never crosses tenants")
        if self.evidence.subject_id != self.binding.subject_id:
            raise ContractViolation(
                f"AssuranceFindingDeclaration.evidence is about subject "
                f"{self.evidence.subject_id!r} but the binding names subject "
                f"{self.binding.subject_id!r}; a finding about one subject is never bound "
                "to another's system identity")
        # The id is *derived*, never chosen. Checking it here is what makes the
        # collision-freedom real: two declarations of different systems, evidence,
        # findings, exercises or windows cannot share an id.
        expected = declaration_id_for(self.binding, self.evidence, self.finding,
                                      self.exercise_ref, self.validity)
        if self.declaration_id != expected:
            raise ContractViolation(
                f"AssuranceFindingDeclaration.declaration_id must be the derived id "
                f"{expected!r}; ids are derived from the binding, evidence, finding, "
                "exercise and window, never chosen by the caller")

    # ------------------------------------------------------------------ #
    @property
    def subject_id(self) -> str:
        return self.binding.subject_id

    @property
    def system_id(self) -> str:
        return self.binding.system_id

    @property
    def system_version(self) -> str:
        return self.binding.system_version

    @property
    def binding_digest(self) -> str:
        return self.binding.canonical_digest()

    @property
    def evidence_id(self) -> str:
        """The evidence reference's own id, read through — the identity both consumer routes share."""

        return self.evidence.evidence_id

    @property
    def evidence_digest(self) -> str:
        return self.evidence.content_digest

    @property
    def evidence_kind(self) -> str:
        return self.evidence.evidence_kind

    @property
    def finding_label(self) -> str:
        """The declared label's text, read through — never copied into a parallel spelling."""

        return self.finding.label

    @property
    def authenticity_status(self) -> SystemBindingAuthenticityStatus:
        """Inherited from the binding, and permanently unverified.

        Exposed so no consumer has to reach past the declaration to discover that
        nothing here is attested.
        """

        return self.binding.authenticity_status

    # ------------------------------------------------------------------ #
    def status_at(self, as_of: datetime) -> ValidityStatus:
        return self.validity.status_at(require_tzaware(as_of, "as_of"))

    def is_declared_at(self, as_of: datetime) -> bool:
        """Inside the window. Outside it the declaration is **absent**, never flagged."""

        return self.status_at(as_of) in (ValidityStatus.FRESH, ValidityStatus.STALE)

    # ------------------------------------------------------------------ #
    def declared_terms(self) -> dict:
        """What was declared, without the window, the lineage or the annotations.

        This is what a supersession must change: the same system, evidence, finding
        and exercise re-declared is an unchanged declaration.
        """

        return {
            "binding_digest": self.binding.canonical_digest(),
            "evidence": _evidence_identity(self.evidence),
            "finding": self.finding.canonical_digest(),
            "exercise_ref": self.exercise_ref,
        }

    def to_dict(self) -> dict:
        return {
            "declaration_id": self.declaration_id,
            "tenant_id": self.tenant_id,
            "binding_digest": self.binding.canonical_digest(),
            "subject_id": self.binding.subject_id,
            "system_id": self.binding.system_id,
            "system_version": self.binding.system_version,
            "evidence_id": self.evidence.evidence_id,
            "evidence_digest": self.evidence.content_digest,
            "evidence_kind": self.evidence.evidence_kind,
            "finding_label": self.finding.label,
            "exercise_ref": self.exercise_ref,
            "validity": validity_to_dict(self.validity),
            "supersedes": self.supersedes,
            "declared_by": self.declared_by,
            "correlation_id": self.correlation_id,
            "notes": self.notes,
        }

    def record_digest(self) -> str:
        return domain_digest("declaration", self.to_dict())


def supersession_refusals(declaration: AssuranceFindingDeclaration,
                          predecessor: Optional[AssuranceFindingDeclaration]) -> tuple[str, ...]:
    """Why a superseding declaration is inadmissible; empty means admissible.

    A supersession is about the *same system*: a finding about a different system
    identity is a new declaration, not a replacement. It must stay in one tenant,
    and it must change something — an unchanged declaration has nothing to
    supersede. A re-run exercise that produced new evidence is exactly a change.
    """

    if not declaration.supersedes:
        return ()
    if predecessor is None:
        return ("the superseded declaration does not exist",)
    reasons: list[str] = []
    if predecessor.declaration_id != declaration.supersedes:
        reasons.append("supersedes does not name the presented predecessor")
    if predecessor.tenant_id != declaration.tenant_id:
        reasons.append("a supersession may not cross tenants")
    if predecessor.binding_digest != declaration.binding_digest:
        reasons.append(
            "a superseding declaration must concern the same system identity; a "
            "different system is a new declaration, not a replacement")
    if predecessor.declared_terms() == declaration.declared_terms():
        reasons.append(
            "a superseding declaration must change what was declared; an unchanged "
            "declaration has nothing to supersede")
    return tuple(reasons)


def require_admissible_supersession(declaration: AssuranceFindingDeclaration,
                                    predecessor: Optional[AssuranceFindingDeclaration]) -> None:
    """Raise :class:`DeclarationSupersessionError` when the supersession is refused."""

    reasons = supersession_refusals(declaration, predecessor)
    if reasons:
        raise DeclarationSupersessionError("; ".join(reasons))
