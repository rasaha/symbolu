"""The vendor-dependency declaration — the only thing this package holds.

A :class:`VendorDependencyDeclaration` says *this tenant declared that this exact
AI system depends on the vendor behind this reference, under this posture, under
this policy, for this window*. It says nothing else, and it can prove nothing the
binding and the label inside it cannot.

**The identity and the vocabulary are not ours.** The record binds an
``AssessedSystemBinding`` and a ``VendorRiskLabel`` **re-exported from
governance-contracts** rather than parallel spellings — the direction that
package fixes itself: engines bind the same system identity "rather than minting
a parallel one. Consumers re-export it; they never redefine it"
(``packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:17-18``),
and the label was landed there first so that every engine carries the same type
(VR-5).

**Binding only (VR-2).** A declaration binds directly to exactly one canonical
binding. A registry registration is neither required nor accepted as an
alternative identity, and the registry is never imported.

**And their ceilings are ours.** A binding proves internal consistency and
digest-bound identity only (``system_identity.py:36-45``); ``authenticity_status``
is permanently unverified. A label is the posture a declarer *assigned*, never a
measure of risk (VR-3). So a declaration records **what a declarer asserted**. It
attests nothing and it never reaches the vendor: ``vendor_ref`` is an opaque,
non-secret reference in the caller's own spelling (VR-5).

**The policy link is a string (VR-4).** ``policy_ref`` names a Policy Authority
version by reference, in the shape of ``policy_refs`` on the neutral action
request. Nothing here resolves, verifies, interprets or fetches it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    SystemBindingAuthenticityStatus,
    Validity,
    ValidityStatus,
    VendorRiskLabel,
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
    "VendorDependencyDeclaration", "DECLARATION_ID_PREFIX", "declaration_id_for",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
]

DECLARATION_ID_PREFIX = "vdd_"


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


def declaration_id_for(binding: AssessedSystemBinding, vendor_ref: str,
                       risk_posture: VendorRiskLabel, policy_ref: str,
                       validity: Validity) -> str:
    """Deterministic declaration id: no UUID, no clock.

    Derived from the binding's own canonical digest, the vendor reference, the
    label's digest, the policy reference and the window, so two loads of the same
    declaration are the same declaration, and a different system, vendor, posture
    or policy can never share an id.
    """

    if not isinstance(binding, AssessedSystemBinding):
        raise ContractViolation("declaration_id_for.binding must be an AssessedSystemBinding")
    if not isinstance(risk_posture, VendorRiskLabel):
        raise ContractViolation("declaration_id_for.risk_posture must be a VendorRiskLabel")
    if not isinstance(validity, Validity):
        raise ContractViolation("declaration_id_for.validity must be a governance-contracts Validity")
    return DECLARATION_ID_PREFIX + domain_digest("declaration_id", {
        "binding": binding.canonical_digest(),
        "vendor_ref": require_nonempty(vendor_ref, "vendor_ref"),
        "risk_posture": risk_posture.canonical_digest(),
        "policy_ref": require_nonempty(policy_ref, "policy_ref"),
        "validity": validity_to_dict(validity),
    })[:32]


@dataclass(frozen=True)
class VendorDependencyDeclaration:
    """One declared vendor dependency, of one exact AI system, for one bounded window."""

    declaration_id: str
    #: The declaring tenant. Must agree with the binding's tenant; a mismatch is
    #: refused at construction rather than silently resolved either way.
    tenant_id: str
    #: Exactly one canonical binding (VR-2). Never a registry registration.
    binding: AssessedSystemBinding
    #: An opaque, non-secret reference to the vendor in the caller's own spelling
    #: (VR-5). Never an address, credential or endpoint: nothing here can reach it.
    vendor_ref: str
    #: The posture the declarer assigned. **Uninterpreted** (VR-3): the package
    #: records it and reasons about it never.
    risk_posture: VendorRiskLabel
    #: One opaque Policy Authority reference (VR-4). Recorded, never resolved.
    policy_ref: str
    validity: Validity
    #: The declaration this one replaces. A changed declaration is made afresh;
    #: the prior record is never edited.
    supersedes: str = ""
    declared_by: str = ""
    correlation_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("declaration_id", "tenant_id", "vendor_ref", "policy_ref"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name),
                                                f"VendorDependencyDeclaration.{name}"))
        for name in ("supersedes", "declared_by", "correlation_id", "notes"):
            object.__setattr__(self, name,
                               optional_text(getattr(self, name),
                                             f"VendorDependencyDeclaration.{name}"))
        if not isinstance(self.binding, AssessedSystemBinding):
            raise ContractViolation(
                "VendorDependencyDeclaration.binding must be a governance-contracts "
                "AssessedSystemBinding; this package mints no system identity of its own "
                "and accepts no inventory record in its place")
        if not isinstance(self.risk_posture, VendorRiskLabel):
            raise ContractViolation(
                "VendorDependencyDeclaration.risk_posture must be a governance-contracts "
                "VendorRiskLabel; this package mints no vocabulary of its own")
        if not isinstance(self.validity, Validity):
            raise ContractViolation(
                "VendorDependencyDeclaration.validity must be a governance-contracts Validity")
        if self.tenant_id != self.binding.tenant_id:
            raise ContractViolation(
                f"VendorDependencyDeclaration.tenant_id {self.tenant_id!r} does not match "
                f"the binding's tenant {self.binding.tenant_id!r}; a declaration never "
                "crosses tenants")
        # The id is *derived*, never chosen. Checking it here is what makes the
        # collision-freedom real: two declarations of different systems, vendors,
        # postures, policies or windows cannot share an id, so a collection keyed
        # by id can never silently lose one.
        expected = declaration_id_for(self.binding, self.vendor_ref, self.risk_posture,
                                      self.policy_ref, self.validity)
        if self.declaration_id != expected:
            raise ContractViolation(
                f"VendorDependencyDeclaration.declaration_id must be the derived id "
                f"{expected!r}; ids are derived from the binding, vendor, posture, policy "
                "and window, never chosen by the caller")

    # ------------------------------------------------------------------ #
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
    def risk_posture_label(self) -> str:
        """The declared posture's text, read through — never copied into a parallel spelling."""

        return self.risk_posture.label

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

        This is what a supersession must change: the same system, vendor, posture
        and policy re-declared is an unchanged declaration.
        """

        return {
            "binding_digest": self.binding.canonical_digest(),
            "vendor_ref": self.vendor_ref,
            "risk_posture": self.risk_posture.canonical_digest(),
            "policy_ref": self.policy_ref,
        }

    def to_dict(self) -> dict:
        return {
            "declaration_id": self.declaration_id,
            "tenant_id": self.tenant_id,
            "binding_digest": self.binding.canonical_digest(),
            "system_id": self.binding.system_id,
            "system_version": self.binding.system_version,
            "vendor_ref": self.vendor_ref,
            "risk_posture_label": self.risk_posture.label,
            "policy_ref": self.policy_ref,
            "validity": validity_to_dict(self.validity),
            "supersedes": self.supersedes,
            "declared_by": self.declared_by,
            "correlation_id": self.correlation_id,
            "notes": self.notes,
        }

    def record_digest(self) -> str:
        return domain_digest("declaration", self.to_dict())


def supersession_refusals(declaration: VendorDependencyDeclaration,
                          predecessor: Optional[VendorDependencyDeclaration]) -> tuple[str, ...]:
    """Why a superseding declaration is inadmissible; empty means admissible.

    A supersession is about the *same vendor*: a declaration for a different vendor
    is a new declaration, not a replacement. It must stay in one tenant, and it
    must change something — an unchanged declaration has nothing to supersede.
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
    if predecessor.vendor_ref != declaration.vendor_ref:
        reasons.append(
            "a superseding declaration must concern the same vendor; a different vendor "
            "is a new declaration, not a replacement")
    if predecessor.declared_terms() == declaration.declared_terms():
        reasons.append(
            "a superseding declaration must change what was declared; an unchanged "
            "declaration has nothing to supersede")
    return tuple(reasons)


def require_admissible_supersession(declaration: VendorDependencyDeclaration,
                                    predecessor: Optional[VendorDependencyDeclaration]) -> None:
    """Raise :class:`DeclarationSupersessionError` when the supersession is refused."""

    reasons = supersession_refusals(declaration, predecessor)
    if reasons:
        raise DeclarationSupersessionError("; ".join(reasons))
