"""The data-use declaration — the only thing this package holds.

A :class:`DataUseDeclaration` says *this tenant declared that this exact AI
system uses the data behind this reference, called this, for this purpose, for
this window*. It says nothing else, and it can prove nothing the binding and the
label inside it cannot.

**The identity and the vocabulary are not ours.** The record binds an
``AssessedSystemBinding`` and a ``DataClassificationLabel`` **re-exported from
governance-contracts** rather than parallel spellings — the direction that
package fixes itself: engines bind the same system identity "rather than minting
a parallel one. Consumers re-export it; they never redefine it"
(``packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:17-18``),
and the label was landed there first precisely so that every engine carries the
same type (DE-5).

**And their ceilings are ours.** A binding proves internal consistency and
digest-bound identity only (``system_identity.py:36-45``); ``authenticity_status``
is permanently unverified. A label is what a declarer *called* the data, never
what that means (DE-3). So a declaration records **what a declarer asserted**. It
attests nothing, and it never sees the data: ``data_ref`` is an opaque, non-secret
reference, and there is no field that could carry a payload.

**Residency is metadata here, never a verdict (DE-2).** ``residency_label`` is
recorded stripped and uninterpreted. ActionGate's ``allowed_region`` constraint
and Model Selection's ``data_residency_allowed`` eligibility gate keep evaluating
residency for their own questions; this package imports neither and answers
neither.

**Admission only (DE-1).** A declaration describes data at the seam *before* it
enters a governed context. Nothing here describes, records or governs what leaves
a model afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    DataClassificationLabel,
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
    "DataUseDeclaration", "DECLARATION_ID_PREFIX", "declaration_id_for",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    "binding_to_dict", "binding_from_dict",
    "declaration_record", "declaration_from_record",
]

#: The binding's own fields, split by shape so a record round-trips exactly.
_BINDING_TEXT_FIELDS = ("binding_id", "tenant_id", "subject_id", "context_id",
                        "context_digest", "system_id", "system_version",
                        "configuration_id", "configuration_digest",
                        "deployment_environment_ref")
_BINDING_INSTANT_FIELDS = ("bound_at",)

DECLARATION_ID_PREFIX = "dud_"


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


def declaration_id_for(binding: AssessedSystemBinding, data_ref: str,
                       classification: DataClassificationLabel, purpose_label: str,
                       validity: Validity) -> str:
    """Deterministic declaration id: no UUID, no clock.

    Derived from the binding's own canonical digest, the data reference, the
    label's digest, the purpose and the window, so two loads of the same
    declaration are the same declaration, and a different system, different data,
    a different label or a different purpose can never share an id.
    """

    if not isinstance(binding, AssessedSystemBinding):
        raise ContractViolation("declaration_id_for.binding must be an AssessedSystemBinding")
    if not isinstance(classification, DataClassificationLabel):
        raise ContractViolation(
            "declaration_id_for.classification must be a DataClassificationLabel")
    if not isinstance(validity, Validity):
        raise ContractViolation("declaration_id_for.validity must be a governance-contracts Validity")
    return DECLARATION_ID_PREFIX + domain_digest("declaration_id", {
        "binding": binding.canonical_digest(),
        "data_ref": require_nonempty(data_ref, "data_ref"),
        "classification": classification.canonical_digest(),
        "purpose_label": require_nonempty(purpose_label, "purpose_label"),
        "validity": validity_to_dict(validity),
    })[:32]


@dataclass(frozen=True)
class DataUseDeclaration:
    """One declared data use, by one exact AI system, for one bounded window."""

    declaration_id: str
    #: The declaring tenant. Must agree with the binding's tenant; a mismatch is
    #: refused at construction rather than silently resolved either way.
    tenant_id: str
    binding: AssessedSystemBinding
    #: An opaque, non-secret reference to the data or the data subject — a dataset
    #: id, a record locator, a subject handle in the caller's own spelling. Never
    #: the data itself: there is no field that could carry a payload.
    data_ref: str
    #: What the declarer called the data. **Uninterpreted** (DE-3): the package
    #: records it and reasons about it never.
    classification: DataClassificationLabel
    #: What the declarer said the data is for. Uninterpreted in the same way.
    purpose_label: str
    validity: Validity
    #: Declared residency metadata, recorded and never evaluated (DE-2).
    residency_label: str = ""
    #: The declaration this one replaces. A changed declaration is made afresh;
    #: the prior record is never edited.
    supersedes: str = ""
    declared_by: str = ""
    correlation_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("declaration_id", "tenant_id", "data_ref", "purpose_label"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"DataUseDeclaration.{name}"))
        for name in ("residency_label", "supersedes", "declared_by", "correlation_id", "notes"):
            object.__setattr__(self, name,
                               optional_text(getattr(self, name), f"DataUseDeclaration.{name}"))
        if not isinstance(self.binding, AssessedSystemBinding):
            raise ContractViolation(
                "DataUseDeclaration.binding must be a governance-contracts "
                "AssessedSystemBinding; this package mints no system identity of its own")
        if not isinstance(self.classification, DataClassificationLabel):
            raise ContractViolation(
                "DataUseDeclaration.classification must be a governance-contracts "
                "DataClassificationLabel; this package mints no vocabulary of its own")
        if not isinstance(self.validity, Validity):
            raise ContractViolation(
                "DataUseDeclaration.validity must be a governance-contracts Validity")
        if self.tenant_id != self.binding.tenant_id:
            raise ContractViolation(
                f"DataUseDeclaration.tenant_id {self.tenant_id!r} does not match the "
                f"binding's tenant {self.binding.tenant_id!r}; a declaration never "
                "crosses tenants")
        # The id is *derived*, never chosen. Checking it here is what makes the
        # collision-freedom real: two declarations of different systems, data,
        # labels, purposes or windows cannot share an id, so a collection keyed by
        # id can never silently lose one.
        expected = declaration_id_for(self.binding, self.data_ref, self.classification,
                                      self.purpose_label, self.validity)
        if self.declaration_id != expected:
            raise ContractViolation(
                f"DataUseDeclaration.declaration_id must be the derived id "
                f"{expected!r}; ids are derived from the binding, data, label, purpose "
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
    def classification_label(self) -> str:
        """The declared label's text, read through — never copied into a parallel spelling."""

        return self.classification.label

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

        This is what a supersession must change: the same system, data, label,
        purpose and residency re-declared is an unchanged declaration.
        """

        return {
            "binding_digest": self.binding.canonical_digest(),
            "data_ref": self.data_ref,
            "classification": self.classification.canonical_digest(),
            "purpose_label": self.purpose_label,
            "residency_label": self.residency_label,
        }

    def to_dict(self) -> dict:
        return {
            "declaration_id": self.declaration_id,
            "tenant_id": self.tenant_id,
            "binding_digest": self.binding.canonical_digest(),
            "system_id": self.binding.system_id,
            "system_version": self.binding.system_version,
            "data_ref": self.data_ref,
            "classification_label": self.classification.label,
            "purpose_label": self.purpose_label,
            "validity": validity_to_dict(self.validity),
            "residency_label": self.residency_label,
            "supersedes": self.supersedes,
            "declared_by": self.declared_by,
            "correlation_id": self.correlation_id,
            "notes": self.notes,
        }

    def record_digest(self) -> str:
        return domain_digest("declaration", self.to_dict())


def binding_to_dict(binding: AssessedSystemBinding) -> dict:
    """The binding's own fields, instants as ISO-8601 UTC text or ``""``."""

    if not isinstance(binding, AssessedSystemBinding):
        raise ContractViolation(
            "binding_to_dict takes a governance-contracts AssessedSystemBinding")
    out = {name: getattr(binding, name) for name in _BINDING_TEXT_FIELDS
           if hasattr(binding, name)}
    for name in _BINDING_INSTANT_FIELDS:
        if not hasattr(binding, name):
            continue
        value = getattr(binding, name)
        out[name] = iso(value, f"AssessedSystemBinding.{name}") if value is not None else ""
    return out


def binding_from_dict(d: dict) -> AssessedSystemBinding:
    """Rebuild a binding from :func:`binding_to_dict`. Any contract failure is this
    package's :class:`ContractViolation`, never a raw neighbour error."""

    if not isinstance(d, dict):
        raise ContractViolation("binding_from_dict takes a mapping")
    unknown = set(d) - set(_BINDING_TEXT_FIELDS) - set(_BINDING_INSTANT_FIELDS)
    if unknown:
        raise ContractViolation(f"binding has unknown fields: {sorted(unknown)}")
    kwargs: dict = {name: d[name] for name in _BINDING_TEXT_FIELDS if name in d}
    for name in _BINDING_INSTANT_FIELDS:
        raw = d.get(name, "")
        if raw in ("", None):
            continue
        if not isinstance(raw, str):
            raise ContractViolation(f"binding.{name} must be ISO-8601 text or empty")
        try:
            kwargs[name] = from_iso(raw)
        except Exception as exc:  # noqa: BLE001 - a malformed instant is a refusal
            raise ContractViolation(
                f"binding.{name} is not an ISO-8601 instant: {exc}") from exc
    try:
        return AssessedSystemBinding(**kwargs)
    except ContractViolation:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"binding refused: {exc}") from exc


def declaration_record(declaration: DataUseDeclaration) -> dict:
    """The complete, reconstructible record: the declaration's own fields plus the
    binding's, under two keys so neither can be mistaken for the other."""

    return {"declaration": declaration.to_dict(),
            "binding": binding_to_dict(declaration.binding)}


def declaration_from_record(record: dict) -> DataUseDeclaration:
    """Rebuild a declaration from :func:`declaration_record`. The derived id is
    re-verified at construction, so an altered record cannot reconstruct."""

    if not isinstance(record, dict) or "declaration" not in record or "binding" not in record:
        raise ContractViolation("a declaration record carries 'declaration' and 'binding'")
    declared = record["declaration"]
    if not isinstance(declared, dict):
        raise ContractViolation("declaration must be a mapping")
    bound = binding_from_dict(record["binding"])
    validity = validity_from_dict(declared.get("validity"))
    if validity is None:
        raise ContractViolation("declaration.validity is required")
    try:
        return DataUseDeclaration(
            declaration_id=declared.get("declaration_id", ""),
            tenant_id=declared.get("tenant_id", ""), binding=bound,
            data_ref=declared.get("data_ref", ""),
            classification=DataClassificationLabel(declared.get("classification_label", "")),
            purpose_label=declared.get("purpose_label", ""), validity=validity,
            residency_label=declared.get("residency_label", ""),
            supersedes=declared.get("supersedes", ""),
            declared_by=declared.get("declared_by", ""),
            correlation_id=declared.get("correlation_id", ""), notes=declared.get("notes", ""))
    except ContractViolation:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"declaration refused: {exc}") from exc


def supersession_refusals(declaration: DataUseDeclaration,
                          predecessor: Optional[DataUseDeclaration]) -> tuple[str, ...]:
    """Why a superseding declaration is inadmissible; empty means admissible.

    A supersession is about the *same data*: a declaration for different data is a
    new declaration, not a replacement. It must stay in one tenant, and it must
    change something — an unchanged declaration has nothing to supersede.
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
    if predecessor.data_ref != declaration.data_ref:
        reasons.append(
            "a superseding declaration must concern the same data; different data is "
            "a new declaration, not a replacement")
    if predecessor.declared_terms() == declaration.declared_terms():
        reasons.append(
            "a superseding declaration must change what was declared; an unchanged "
            "declaration has nothing to supersede")
    return tuple(reasons)


def require_admissible_supersession(declaration: DataUseDeclaration,
                                    predecessor: Optional[DataUseDeclaration]) -> None:
    """Raise :class:`DeclarationSupersessionError` when the supersession is refused."""

    reasons = supersession_refusals(declaration, predecessor)
    if reasons:
        raise DeclarationSupersessionError("; ".join(reasons))
