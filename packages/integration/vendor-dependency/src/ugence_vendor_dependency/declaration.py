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
from .version import CONTRACT_VERSION, LEGACY_CONTRACT_VERSION
from .vocabulary import (
    VocabularyBinding,
    VocabularyBindingState,
    vocabulary_binding_from_dict,
    vocabulary_binding_to_dict,
)

__all__ = [
    "VendorDependencyDeclaration", "DECLARATION_ID_PREFIX", "declaration_id_for",
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
                       validity: Validity,
                       posture_vocabulary: Optional[VocabularyBinding] = None) -> str:
    """Deterministic declaration id: no UUID, no clock.

    Derived from the binding's own canonical digest, the vendor reference, the
    label's digest, the policy reference and the window, so two loads of the same
    declaration are the same declaration, and a different system, vendor, posture
    or policy can never share an id.

    **Since v2 the posture vocabulary is part of it** (``VV-C``). The posture already
    participates in this record's identity, so the vocabulary it was read under
    participates too: two declarations naming the same member of two different
    vocabulary versions are two declarations. This is one of the two records where
    ``VV-C`` answers yes, and it answers yes for that reason rather than by default.

    **The v1 preimage is reproduced exactly when no binding is given** — the key is
    added rather than the shape rewritten — so a historical record still derives the id
    it was stored under (``VV-B``: historical digests are never recomputed under the new
    projection).
    """

    if not isinstance(binding, AssessedSystemBinding):
        raise ContractViolation("declaration_id_for.binding must be an AssessedSystemBinding")
    if not isinstance(risk_posture, VendorRiskLabel):
        raise ContractViolation("declaration_id_for.risk_posture must be a VendorRiskLabel")
    if not isinstance(validity, Validity):
        raise ContractViolation("declaration_id_for.validity must be a governance-contracts Validity")
    preimage = {
        "binding": binding.canonical_digest(),
        "vendor_ref": require_nonempty(vendor_ref, "vendor_ref"),
        "risk_posture": risk_posture.canonical_digest(),
        "policy_ref": require_nonempty(policy_ref, "policy_ref"),
        "validity": validity_to_dict(validity),
    }
    if posture_vocabulary is not None:
        preimage["posture_vocabulary"] = vocabulary_binding_to_dict(posture_vocabulary)
    return DECLARATION_ID_PREFIX + domain_digest("declaration_id", preimage)[:32]


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
    #:
    #: **It does not carry the vocabulary reference below, and PUB-2 says why.** That
    #: reuse was authorized only if ``policy_ref`` normatively identified the exact
    #: vocabulary, and VR-4 forbids this package from resolving or interpreting it at
    #: all — so it references *some* policy, with no guarantee which. Two fields, two
    #: jobs.
    policy_ref: str
    validity: Validity
    #: The published vocabulary ``risk_posture`` was written against. Required on a v2
    #: record (``VV-E``); ``""``, ``latest`` and ``current`` are refused, since a moving
    #: reference records nothing durable.
    posture_vocabulary: Optional[VocabularyBinding] = None
    #: Which record shape this is. A caller never chooses it for new work — it defaults
    #: to the current contract, and the only other accepted value reconstructs a
    #: historical record that already exists.
    record_version: str = CONTRACT_VERSION
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
        self._require_vocabulary_binding()
        # The id is *derived*, never chosen. Checking it here is what makes the
        # collision-freedom real: two declarations of different systems, vendors,
        # postures, policies or windows cannot share an id, so a collection keyed
        # by id can never silently lose one.
        expected = declaration_id_for(self.binding, self.vendor_ref, self.risk_posture,
                                      self.policy_ref, self.validity,
                                      self.posture_vocabulary)
        if self.declaration_id != expected:
            raise ContractViolation(
                f"VendorDependencyDeclaration.declaration_id must be the derived id "
                f"{expected!r}; ids are derived from the binding, vendor, posture, policy "
                "and window, never chosen by the caller")

    def _require_vocabulary_binding(self) -> None:
        """``VV-E``: required on a new record version, absent only on a historical one.

        The two cases are exclusive by construction, so there is no third shape and no
        way to write a current record without naming the vocabulary its posture was read
        under.
        """

        if self.record_version not in (CONTRACT_VERSION, LEGACY_CONTRACT_VERSION):
            raise ContractViolation(
                f"VendorDependencyDeclaration.record_version {self.record_version!r} is "
                f"neither the current contract {CONTRACT_VERSION!r} nor the historical "
                f"{LEGACY_CONTRACT_VERSION!r}")
        if (self.posture_vocabulary is not None
                and not isinstance(self.posture_vocabulary, VocabularyBinding)):
            raise ContractViolation(
                "VendorDependencyDeclaration.posture_vocabulary must be a VocabularyBinding")
        if self.record_version == LEGACY_CONTRACT_VERSION:
            if self.posture_vocabulary is not None:
                raise ContractViolation(
                    f"a {LEGACY_CONTRACT_VERSION} declaration carries no vocabulary "
                    "binding; a record that names a vocabulary is a current record, and "
                    "its digest and id are derived under the current projection")
            return
        if self.posture_vocabulary is None:
            raise ContractViolation(
                "VendorDependencyDeclaration requires posture_vocabulary: a governed "
                "label on a current record names the published vocabulary it was written "
                "against (VV-E). policy_ref does not stand in for it — VR-4 makes that "
                "string opaque, and PUB-2 ruled that an opaque reference identifies no "
                "vocabulary in particular. An absent reference is never defaulted to the "
                "current vocabulary")

    # ------------------------------------------------------------------ #
    @property
    def vocabulary_state(self) -> VocabularyBindingState:
        """Whether this record names its vocabulary, or predates the requirement.

        ``UNVERSIONED_LEGACY`` says the taxonomy is **unknown**, and ``VV-E`` forbids
        resolving it to any published vocabulary.
        """

        return (VocabularyBindingState.BOUND if self.posture_vocabulary is not None
                else VocabularyBindingState.UNVERSIONED_LEGACY)

    @property
    def is_current_record(self) -> bool:
        return self.record_version == CONTRACT_VERSION

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

        **The vocabulary is part of the terms.** Re-declaring the same posture under a
        new vocabulary version *is* a change: the words are identical and what they were
        read to mean is not. Leaving the binding out here would refuse exactly the
        supersession a vocabulary revision exists to record.
        """

        return {
            "binding_digest": self.binding.canonical_digest(),
            "vendor_ref": self.vendor_ref,
            "risk_posture": self.risk_posture.canonical_digest(),
            "policy_ref": self.policy_ref,
            "posture_vocabulary": vocabulary_binding_to_dict(self.posture_vocabulary),
        }

    def to_dict(self) -> dict:
        """The canonical projection, from an explicit key list rather than ``asdict``.

        A v1 record projects the v1 keys and nothing else, so its stored digest still
        verifies byte for byte; a v2 record adds the binding and the record version.
        """

        projected = {
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
        if self.record_version == LEGACY_CONTRACT_VERSION:
            return projected
        projected["record_version"] = self.record_version
        projected["posture_vocabulary"] = vocabulary_binding_to_dict(self.posture_vocabulary)
        return projected

    def record_digest(self) -> str:
        """The digest of the whole projection, the vocabulary included on a v2 record.

        ``VV-B``: a digest excluding the taxonomy would prove the *bytes* of a label
        while failing to prove what that label meant, and two otherwise identical
        records written under different vocabulary versions must not collide.
        """

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


def declaration_record(declaration: VendorDependencyDeclaration) -> dict:
    """The complete, reconstructible record: the declaration's own fields plus the
    binding's, under two keys so neither can be mistaken for the other."""

    return {"declaration": declaration.to_dict(),
            "binding": binding_to_dict(declaration.binding)}


def declaration_from_record(record: dict) -> VendorDependencyDeclaration:
    """Rebuild a declaration from :func:`declaration_record`. The derived id is
    re-verified at construction, so an altered record cannot reconstruct.

    A record written before the binding still reads: its version is discovered from the
    record itself, it projects the v1 keys, it derives the id it was stored under, and
    it comes back ``UNVERSIONED_LEGACY`` rather than quietly upgraded (``VV-E``).
    """

    if not isinstance(record, dict) or "declaration" not in record or "binding" not in record:
        raise ContractViolation("a declaration record carries 'declaration' and 'binding'")
    declared = record["declaration"]
    if not isinstance(declared, dict):
        raise ContractViolation("declaration must be a mapping")
    bound = binding_from_dict(record["binding"])
    validity = validity_from_dict(declared.get("validity"))
    if validity is None:
        raise ContractViolation("declaration.validity is required")
    # A record with no stored version predates the field, so it is v1 by construction —
    # inferred from its own absence rather than from the reader's current contract,
    # which is what would silently reinterpret an old record.
    record_version = declared.get("record_version") or LEGACY_CONTRACT_VERSION
    try:
        return VendorDependencyDeclaration(
            declaration_id=declared.get("declaration_id", ""),
            tenant_id=declared.get("tenant_id", ""), binding=bound,
            vendor_ref=declared.get("vendor_ref", ""),
            risk_posture=VendorRiskLabel(declared.get("risk_posture_label", "")),
            policy_ref=declared.get("policy_ref", ""), validity=validity,
            posture_vocabulary=vocabulary_binding_from_dict(
                declared.get("posture_vocabulary"), "declaration.posture_vocabulary"),
            record_version=record_version,
            supersedes=declared.get("supersedes", ""),
            declared_by=declared.get("declared_by", ""),
            correlation_id=declared.get("correlation_id", ""), notes=declared.get("notes", ""))
    except ContractViolation:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"declaration refused: {exc}") from exc


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
