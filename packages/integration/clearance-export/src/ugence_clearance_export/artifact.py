"""The exported artifact: a received clearance, plus what a reader can check about it.

Three enums, each with exactly one member, each on the
``SystemBindingAuthenticityStatus`` precedent (governance-contracts
``contracts/system_identity.py:217``, whose docstring records why a second member
is deliberately absent). One member is not a placeholder here; it is the honest
size of what the platform can currently establish, and the artifact says so in
three separate places because the three claims are independent:

* :class:`IdentityAssurance` — who the declarers upstream were (CE-3)
* :class:`ExportAuthenticity` — whether the producer is who it claims (CE-4)
* :class:`ExportDataClassification` — whether the clearance is real (CE-7, §13.1)

None of the three may be inferred from the absence of another, and none is
omittable: they are required constructor arguments, validated against the single
admissible member, and always serialized. A caller cannot build an artifact
without stating all three, and cannot state anything but the truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Tuple

from ugence_action_clearance import ClearanceReceiptBody, ClearanceStatus

from ._canon import canonical_json, domain_digest, from_iso, iso, require_nonempty
from .errors import (
    AuthenticityClaimRefused,
    ClassificationClaimRefused,
    ContractViolation,
    IdentityAssuranceClaimRefused,
    NotAReceivedClearance,
)

__all__ = [
    "ARTIFACT_ID_PREFIX",
    "AUTHENTICITY_PREREQUISITE",
    "COMPILE_SHAPED_KEYS",
    "ClearanceExportArtifact",
    "ExportAuthenticity",
    "ExportDataClassification",
    "IdentityAssurance",
    "artifact_from_dict",
    "artifact_to_dict",
    "build_export",
    "receipt_body_from_dict",
    "receipt_body_to_dict",
]

#: Content-addressed identity prefix, on the ``acr_`` precedent in action-clearance.
ARTIFACT_ID_PREFIX = "cxp_"

#: CE-4 names the unfed prerequisite rather than leaving a consumer to discover it.
#: The resolver contract exists; nothing feeds it.
AUTHENTICITY_PREREQUISITE = (
    "TrustAnchorResolverPort exists in trusted-evidence-authority and no signing "
    "key or trust root is configured; content-addressing establishes integrity, "
    "never authenticity."
)

#: CE-1, held structurally. A compile result is not a clearance: it establishes
#: what was compiled, not whether a consequential action may proceed now and until
#: when. These are the keys a compile result carries; an artifact that accepted one
#: would be serializing the wrong question under the right name.
COMPILE_SHAPED_KEYS: Tuple[str, ...] = (
    "logical_digest",
    "workflow_ir",
    "compiled_at",
    "compilation_id",
)


class IdentityAssurance(str, Enum):
    """How much the identities upstream of this clearance actually prove.

    The enum has exactly **one** member because exactly one thing is provable
    today. Every declarer that reaches a clearance — registration, data-use,
    vendor — is recorded as having *presented* an identity that nothing verified.

    A second member (an authority-verified assurance) is deliberately **absent**:
    admitting one would require an enterprise issuer that does not exist, and an
    enum that offered it would invite a consumer to look for a value the platform
    can never set, and a producer to set it anyway. Adding it later is additive
    and takes a ruling (CE-3).
    """

    #: The declarers presented an identity; no authority verified it, and none is
    #: claimed. This ceiling travels with the artifact rather than evaporating at
    #: the serialization boundary.
    PRESENTED_UNPROVEN = "PRESENTED_UNPROVEN"


class ExportAuthenticity(str, Enum):
    """Whether a reader can establish that the producer is who it claims.

    One member, for the reason :data:`AUTHENTICITY_PREREQUISITE` states. A
    fingerprint proves the body was not altered by someone who cannot recompute
    it, which is everyone and no one; it is integrity, and integrity is not
    authenticity (CE-4).
    """

    #: Nothing signed this. Integrity is checkable; authenticity is not.
    UNSIGNED = "UNSIGNED"


class ExportDataClassification(str, Enum):
    """What the clearance inside this artifact is evidence of.

    One member, because at this stage the deployment holds no clearance any
    authority granted (ADR §11.2). A seeded receipt exercises the export path and
    the verifier and is evidence about nothing else: no authority granted it, it
    confers no approval, and it satisfies no obligation (§13.1).
    """

    #: Demonstration data. Not a clearance any authority granted; confers nothing.
    SYNTHETIC_DEMONSTRATION_ONLY = "SYNTHETIC_DEMONSTRATION_ONLY"


def _require_identity_assurance(value: object) -> IdentityAssurance:
    if value is not IdentityAssurance.PRESENTED_UNPROVEN:
        raise IdentityAssuranceClaimRefused(
            "identity_assurance must be PRESENTED_UNPROVEN; no verifier or "
            f"enterprise issuer exists that could establish {value!r}")
    return value


def _require_authenticity(value: object) -> ExportAuthenticity:
    if value is not ExportAuthenticity.UNSIGNED:
        raise AuthenticityClaimRefused(
            f"authenticity must be UNSIGNED; {AUTHENTICITY_PREREQUISITE}")
    return value


def _require_classification(value: object) -> ExportDataClassification:
    if value is not ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY:
        raise ClassificationClaimRefused(
            "data_classification must be SYNTHETIC_DEMONSTRATION_ONLY; the "
            "deployment holds no clearance any authority granted")
    return value


def _require_received_clearance(body: object) -> ClearanceReceiptBody:
    """CE-1: only a received clearance receipt may be exported."""

    if not isinstance(body, ClearanceReceiptBody):
        raise NotAReceivedClearance(
            "only a ClearanceReceiptBody may be exported; a compile result "
            "establishes what was compiled, never whether an action may proceed")
    return body


@dataclass(frozen=True)
class ClearanceExportArtifact:
    """One received clearance, portable, content-addressed, and self-describing.

    The body is Action Clearance's own :class:`ClearanceReceiptBody`, carried
    unaltered — this package re-serializes it and adds no field to it, because the
    receipt is the evaluator partition's projection and gains no transport concern
    from being exported (CE-2).

    Everything else on this record is a statement about what a reader can and
    cannot check.
    """

    artifact_version: str
    body: ClearanceReceiptBody
    identity_assurance: IdentityAssurance
    authenticity: ExportAuthenticity
    authenticity_prerequisite: str
    data_classification: ExportDataClassification
    exported_for_tenant: str
    artifact_fingerprint: str

    def __post_init__(self) -> None:
        _require_received_clearance(self.body)
        _require_identity_assurance(self.identity_assurance)
        _require_authenticity(self.authenticity)
        _require_classification(self.data_classification)
        require_nonempty(self.artifact_version, "artifact_version")
        require_nonempty(self.exported_for_tenant, "exported_for_tenant")
        require_nonempty(self.artifact_fingerprint, "artifact_fingerprint")
        if self.authenticity_prerequisite != AUTHENTICITY_PREREQUISITE:
            raise AuthenticityClaimRefused(
                "authenticity_prerequisite is fixed text and may not be softened")

    @property
    def artifact_id(self) -> str:
        """Content-addressed identity (a hash label, not an acronym)."""

        return ARTIFACT_ID_PREFIX + self.artifact_fingerprint

    @property
    def receipt_id(self) -> str:
        """The identity the exported clearance already had."""

        return self.body.receipt_id


def _body_to_dict(body: ClearanceReceiptBody) -> Dict[str, Any]:
    """The receipt body in transport form, field for field and nothing added."""

    return {
        "receipt_version": body.receipt_version,
        "tenant_id": body.tenant_id,
        "request_id": body.request_id,
        "authorization_ref": body.authorization_ref,
        "authorized_action_fingerprint": body.authorized_action_fingerprint,
        "clearance_status": body.clearance_status.value,
        "reason_codes": list(body.reason_codes),
        "effective_constraints": list(body.effective_constraints),
        "obligations": list(body.obligations),
        "signal_refs": list(body.signal_refs),
        "signal_bundle_fingerprint": body.signal_bundle_fingerprint,
        "policy_refs": list(body.policy_refs),
        "evaluated_at": iso(body.evaluated_at, "ClearanceReceiptBody.evaluated_at"),
        "valid_until": iso(body.valid_until, "ClearanceReceiptBody.valid_until"),
        "request_fingerprint": body.request_fingerprint,
        "result_fingerprint": body.result_fingerprint,
    }


def _body_from_dict(payload: Mapping[str, Any]) -> ClearanceReceiptBody:
    for banned in COMPILE_SHAPED_KEYS:
        if banned in payload:
            raise NotAReceivedClearance(
                f"payload carries the compile-shaped key {banned!r}; a compile "
                "result is not a clearance (CE-1)")
    try:
        return ClearanceReceiptBody(
            receipt_version=payload["receipt_version"],
            tenant_id=payload["tenant_id"],
            request_id=payload["request_id"],
            authorization_ref=payload["authorization_ref"],
            authorized_action_fingerprint=payload["authorized_action_fingerprint"],
            clearance_status=ClearanceStatus(payload["clearance_status"]),
            reason_codes=tuple(payload["reason_codes"]),
            effective_constraints=tuple(payload["effective_constraints"]),
            obligations=tuple(payload["obligations"]),
            signal_refs=tuple(payload["signal_refs"]),
            signal_bundle_fingerprint=payload["signal_bundle_fingerprint"],
            policy_refs=tuple(payload["policy_refs"]),
            evaluated_at=from_iso(payload["evaluated_at"]),
            valid_until=from_iso(payload["valid_until"]),
            request_fingerprint=payload["request_fingerprint"],
            result_fingerprint=payload["result_fingerprint"],
        )
    except KeyError as missing:
        raise ContractViolation(f"receipt body is missing {missing}") from None


def _fingerprint_preimage(
    *,
    artifact_version: str,
    body: ClearanceReceiptBody,
    identity_assurance: IdentityAssurance,
    authenticity: ExportAuthenticity,
    data_classification: ExportDataClassification,
    exported_for_tenant: str,
) -> Dict[str, Any]:
    """Every field the artifact asserts, and nothing else.

    The three honesty labels are inside the preimage deliberately: altering one
    changes the fingerprint, so a consumer that recomputes it detects a stripped
    label exactly as it detects an altered decision (§13.3).
    """

    return {
        "artifact_version": artifact_version,
        "authenticity": authenticity.value,
        "data_classification": data_classification.value,
        "exported_for_tenant": exported_for_tenant,
        "identity_assurance": identity_assurance.value,
        "receipt_body": _body_to_dict(body),
    }


def build_export(
    body: ClearanceReceiptBody,
    *,
    identity_assurance: IdentityAssurance,
    authenticity: ExportAuthenticity,
    data_classification: ExportDataClassification,
    artifact_version: str = "clearance_export.artifact.v1",
) -> ClearanceExportArtifact:
    """Wrap a received clearance receipt as a portable artifact. Pure.

    Reads no clock, opens nothing, and reaches nowhere: the artifact is a function
    of its arguments alone, so exporting the same clearance twice produces the
    same bytes and the same fingerprint.

    The three labels are **required keyword arguments with one admissible value
    each**. That is deliberate: a default could be overridden by a later caller
    who never read this docstring, and an optional field could be dropped by a
    serializer. A caller must state all three, and may state only the truth.
    """

    received = _require_received_clearance(body)
    assurance = _require_identity_assurance(identity_assurance)
    signed = _require_authenticity(authenticity)
    classification = _require_classification(data_classification)
    tenant = require_nonempty(received.tenant_id, "body.tenant_id")

    fingerprint = domain_digest("artifact", _fingerprint_preimage(
        artifact_version=artifact_version,
        body=received,
        identity_assurance=assurance,
        authenticity=signed,
        data_classification=classification,
        exported_for_tenant=tenant,
    ))
    return ClearanceExportArtifact(
        artifact_version=artifact_version,
        body=received,
        identity_assurance=assurance,
        authenticity=signed,
        authenticity_prerequisite=AUTHENTICITY_PREREQUISITE,
        data_classification=classification,
        exported_for_tenant=tenant,
        artifact_fingerprint=fingerprint,
    )


def artifact_to_dict(artifact: ClearanceExportArtifact) -> Dict[str, Any]:
    """Transport form. Every honesty label is present on every artifact, always."""

    return {
        "artifact_id": artifact.artifact_id,
        "artifact_version": artifact.artifact_version,
        "artifact_fingerprint": artifact.artifact_fingerprint,
        "authenticity": artifact.authenticity.value,
        "authenticity_prerequisite": artifact.authenticity_prerequisite,
        "data_classification": artifact.data_classification.value,
        "exported_for_tenant": artifact.exported_for_tenant,
        "identity_assurance": artifact.identity_assurance.value,
        "receipt_id": artifact.receipt_id,
        "receipt_body": _body_to_dict(artifact.body),
    }


def artifact_from_dict(payload: Mapping[str, Any]) -> ClearanceExportArtifact:
    """Rebuild an artifact from transport form, refusing every softened claim.

    A payload that omits a label, or carries one this package does not admit, is
    refused rather than defaulted — the reconstruction path is where a stripped
    label would otherwise re-enter as an innocent-looking absence.
    """

    try:
        assurance = IdentityAssurance(payload["identity_assurance"])
        authenticity = ExportAuthenticity(payload["authenticity"])
        classification = ExportDataClassification(payload["data_classification"])
    except KeyError as missing:
        raise ContractViolation(
            f"artifact is missing the required honesty label {missing}") from None
    except ValueError as bad:
        raise ContractViolation(f"artifact carries an inadmissible label: {bad}") from None

    body = _body_from_dict(payload["receipt_body"])
    rebuilt = build_export(
        body,
        identity_assurance=assurance,
        authenticity=authenticity,
        data_classification=classification,
        artifact_version=payload.get("artifact_version", "clearance_export.artifact.v1"),
    )
    return rebuilt


def canonical_form(artifact: ClearanceExportArtifact) -> str:
    """The exact bytes a consumer fingerprints. Stable across processes and hosts."""

    return canonical_json(_fingerprint_preimage(
        artifact_version=artifact.artifact_version,
        body=artifact.body,
        identity_assurance=artifact.identity_assurance,
        authenticity=artifact.authenticity,
        data_classification=artifact.data_classification,
        exported_for_tenant=artifact.exported_for_tenant,
    ))


#: Public names for the receipt-body transport pair. Exposed deliberately: whoever
#: holds received receipts must parse them, and a second parser somewhere else would
#: be a second definition of a content-addressed record — the thing CE-2 avoids by
#: importing action-clearance rather than redefining its type. Reading a receipt is
#: not writing one: neither of these touches a store.
receipt_body_to_dict = _body_to_dict
receipt_body_from_dict = _body_from_dict
