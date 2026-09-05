"""The registration record — the only thing this package holds.

A :class:`SystemRegistration` says *this organization registered this exact AI
system, owned by this reference, under this declared classification, for this
window*. It says nothing else, and it can prove nothing the binding inside it
cannot.

**The identity is not ours.** The record binds an ``AssessedSystemBinding``
**re-exported from governance-contracts** rather than a parallel spelling — the
direction that module fixes itself: engines bind the same system identity "rather
than minting a parallel one. Consumers re-export it; they never redefine it"
(``packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:17-18``).

**And its ceiling is ours.** A binding proves internal consistency and digest-bound
identity only — never that the named system was deployed, that its configuration
digest was computed over the real configuration, or that a manifest reference
resolves (``system_identity.py:36-45``); ``authenticity_status`` is permanently
unverified. So a registration records **what an administrator asserted**. It
attests nothing.
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
)

from ._canon import (
    domain_digest,
    from_iso,
    iso,
    optional_text,
    require_nonempty,
    require_tzaware,
)
from .errors import ContractViolation, RegistrationSupersessionError

__all__ = [
    "SystemRegistration", "REGISTRATION_ID_PREFIX", "registration_id_for",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
]

REGISTRATION_ID_PREFIX = "reg_"


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


def registration_id_for(binding: AssessedSystemBinding, owner_ref: str,
                        validity: Validity) -> str:
    """Deterministic registration id: no UUID, no clock.

    Derived from the binding's own canonical digest, so two loads of the same
    registration are the same registration, and a different system — or a different
    configuration of it — can never share an id.
    """

    if not isinstance(binding, AssessedSystemBinding):
        raise ContractViolation("registration_id_for.binding must be an AssessedSystemBinding")
    return REGISTRATION_ID_PREFIX + domain_digest("registration_id", {
        "binding": binding.canonical_digest(),
        "owner_ref": require_nonempty(owner_ref, "owner_ref"),
        "validity": validity_to_dict(validity),
    })[:32]


@dataclass(frozen=True)
class SystemRegistration:
    """One registered AI system, for one bounded window."""

    registration_id: str
    binding: AssessedSystemBinding
    #: A non-secret directory handle for the accountable owner. Never a credential,
    #: never an authenticated identity, and never proof that anyone accepted the role.
    owner_ref: str
    #: The classification an administrator declared. **Uninterpreted** (D-2): the
    #: package records it and reasons about it never. A blank label is refused; an
    #: unrecognized one is not, because there is no recognized set.
    classification_label: str
    validity: Validity
    #: The registration this one replaces (D-3). A new system version is registered
    #: afresh; the prior record is never edited.
    supersedes: str = ""
    registered_by: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("registration_id", "owner_ref", "classification_label"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"SystemRegistration.{name}"))
        for name in ("supersedes", "registered_by", "notes"):
            object.__setattr__(self, name,
                               optional_text(getattr(self, name), f"SystemRegistration.{name}"))
        if not isinstance(self.binding, AssessedSystemBinding):
            raise ContractViolation(
                "SystemRegistration.binding must be a governance-contracts "
                "AssessedSystemBinding; this package mints no system identity of its own")
        if not isinstance(self.validity, Validity):
            raise ContractViolation(
                "SystemRegistration.validity must be a governance-contracts Validity")
        # The id is *derived*, never chosen. Checking it here is what makes the
        # collision-freedom real: two registrations of different systems, versions,
        # owners or windows cannot share an id, so a collection keyed by id can
        # never silently lose one.
        expected = registration_id_for(self.binding, self.owner_ref, self.validity)
        if self.registration_id != expected:
            raise ContractViolation(
                f"SystemRegistration.registration_id must be the derived id "
                f"{expected!r}; ids are derived from the binding, owner and window, "
                "never chosen by the caller")

    # ------------------------------------------------------------------ #
    @property
    def tenant_id(self) -> str:
        return self.binding.tenant_id

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
    def authenticity_status(self) -> SystemBindingAuthenticityStatus:
        """Inherited from the binding, and permanently unverified.

        Exposed so no consumer has to reach past the registration to discover that
        nothing here is attested.
        """

        return self.binding.authenticity_status

    # ------------------------------------------------------------------ #
    def status_at(self, as_of: datetime) -> ValidityStatus:
        return self.validity.status_at(require_tzaware(as_of, "as_of"))

    def is_registered_at(self, as_of: datetime) -> bool:
        """Inside the window. Outside it the registration is **absent**, never flagged."""

        return self.status_at(as_of) in (ValidityStatus.FRESH, ValidityStatus.STALE)

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "registration_id": self.registration_id,
            "binding_digest": self.binding.canonical_digest(),
            "tenant_id": self.binding.tenant_id, "system_id": self.binding.system_id,
            "system_version": self.binding.system_version,
            "owner_ref": self.owner_ref, "classification_label": self.classification_label,
            "validity": validity_to_dict(self.validity), "supersedes": self.supersedes,
            "registered_by": self.registered_by, "notes": self.notes,
        }

    def record_digest(self) -> str:
        return domain_digest("registration", self.to_dict())


def supersession_refusals(registration: SystemRegistration,
                          predecessor: Optional[SystemRegistration]) -> tuple[str, ...]:
    """Why a superseding registration is inadmissible; empty means admissible.

    D-3: a registration binds exactly one system identity, and a superseding one must
    bind a *different* binding. A changed system is registered afresh; an unchanged
    one has nothing to supersede.
    """

    if not registration.supersedes:
        return ()
    if predecessor is None:
        return ("the superseded registration does not exist",)
    reasons: list[str] = []
    if predecessor.registration_id != registration.supersedes:
        reasons.append("supersedes does not name the presented predecessor")
    if predecessor.tenant_id != registration.tenant_id:
        reasons.append("a supersession may not cross tenants")
    if predecessor.binding_digest == registration.binding_digest:
        reasons.append(
            "a superseding registration must bind a different system identity; "
            "an unchanged system has nothing to supersede")
    return tuple(reasons)


def require_admissible_supersession(registration: SystemRegistration,
                                    predecessor: Optional[SystemRegistration]) -> None:
    """Raise :class:`RegistrationSupersessionError` when the supersession is refused."""

    reasons = supersession_refusals(registration, predecessor)
    if reasons:
        raise RegistrationSupersessionError("; ".join(reasons))
