"""The pure verifier: what a reader can check, and what it must not conclude.

ADR §6 tabulated five checks an external runtime would want. Exactly one of them
is available today, and the honest thing is to answer all five rather than the one
— a verifier that returned ``True`` and stopped would let a consumer read integrity
as authenticity, which is the confusion CE-4 exists to prevent.

So :func:`verify_export` returns a **report**, not a boolean. It says the artifact
is intact, and in the same breath that intact does not mean signed, does not mean
the declarers were verified, does not mean the policy is in force, and does not
mean any authority granted the clearance.

Pure: no clock, no network, no key material, no store. Everything it concludes it
concludes by recomputing a hash over the bytes it was handed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ugence_action_clearance import ClearanceResult

from ._canon import domain_digest
from .artifact import (
    ARTIFACT_ID_PREFIX,
    ClearanceExportArtifact,
    _fingerprint_preimage,
)
from .errors import ExportIntegrityError

__all__ = [
    "UNCHECKABLE",
    "ExportVerification",
    "verify_export",
]

#: The four things this artifact cannot establish, named on every verification so
#: a consumer never has to infer them from a bare ``True``. ADR §6.
UNCHECKABLE: Tuple[str, ...] = (
    "AUTHENTICITY_NOT_ESTABLISHED: nothing signed this artifact; content-addressing "
    "proves it was not altered, never who produced it",
    "DECLARER_IDENTITY_NOT_VERIFIED: every identity upstream of this clearance is "
    "PRESENTED_UNPROVEN and no issuer exists that could raise that",
    "POLICY_IN_FORCE_NOT_CHECKABLE: policy_refs are references, resolvable only "
    "against the deployment that produced them",
    "APPROVAL_NOT_PROVEN: authorization_ref is a reference, not a proof",
)


@dataclass(frozen=True)
class ExportVerification:
    """What recomputation established, and the four things it did not.

    ``integrity_verified`` is the only positive claim in this record, and it is a
    narrow one: the bytes are the bytes that were fingerprinted. Reading it as
    "this clearance is genuine" is the error :data:`UNCHECKABLE` exists to block.
    """

    integrity_verified: bool
    artifact_id: str
    receipt_id: str
    identity_assurance: str
    authenticity: str
    data_classification: str
    uncheckable: Tuple[str, ...]

    @property
    def confers(self) -> str:
        """What a consumer may do on the strength of this verification. Nothing."""

        return (
            "NOTHING: verification establishes that the artifact is intact. It "
            "grants no permission, satisfies no obligation, and is not an "
            "authority's decision that any action may proceed."
        )


def verify_export(artifact: ClearanceExportArtifact) -> ExportVerification:
    """Recompute the artifact's fingerprint and report what that does and does not show.

    Raises :class:`ExportIntegrityError` when the artifact does not re-derive its
    own fingerprint, when its id does not follow from it, or when the receipt body
    inside it does not re-derive its own ``result_fingerprint`` through Action
    Clearance's public surface. Both layers are checked: an artifact whose wrapper
    is intact and whose clearance was swapped is not intact.
    """

    recomputed = domain_digest("artifact", _fingerprint_preimage(
        artifact_version=artifact.artifact_version,
        body=artifact.body,
        identity_assurance=artifact.identity_assurance,
        authenticity=artifact.authenticity,
        data_classification=artifact.data_classification,
        exported_for_tenant=artifact.exported_for_tenant,
    ))
    if recomputed != artifact.artifact_fingerprint:
        raise ExportIntegrityError(
            "artifact does not re-derive its artifact_fingerprint (altered after export)")
    if artifact.artifact_id != ARTIFACT_ID_PREFIX + artifact.artifact_fingerprint:
        raise ExportIntegrityError("artifact_id does not follow from artifact_fingerprint")

    body = artifact.body
    rebuilt = ClearanceResult(
        request_id=body.request_id,
        authorization_ref=body.authorization_ref,
        authorized_action_fingerprint=body.authorized_action_fingerprint,
        status=body.clearance_status,
        reason_codes=tuple(body.reason_codes),
        effective_constraints=tuple(body.effective_constraints),
        obligations=tuple(body.obligations),
        evaluated_at=body.evaluated_at,
        valid_until=body.valid_until,
        policy_refs=tuple(body.policy_refs),
        signal_refs=tuple(body.signal_refs),
        request_fingerprint=body.request_fingerprint,
        tenant_id=body.tenant_id,
        signal_bundle_fingerprint=body.signal_bundle_fingerprint,
    )
    if rebuilt.result_fingerprint != body.result_fingerprint:
        raise ExportIntegrityError(
            "the exported clearance does not re-derive its result_fingerprint")

    return ExportVerification(
        integrity_verified=True,
        artifact_id=artifact.artifact_id,
        receipt_id=artifact.receipt_id,
        identity_assurance=artifact.identity_assurance.value,
        authenticity=artifact.authenticity.value,
        data_classification=artifact.data_classification.value,
        uncheckable=UNCHECKABLE,
    )
