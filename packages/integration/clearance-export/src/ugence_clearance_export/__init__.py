"""Ugence Clearance Export — a received clearance, made portable and honest about itself.

    THIS PACKAGE SERIALIZES A CLEARANCE SOMEBODY ELSE EVALUATED AND REPORTS WHAT
    A READER CAN CHECK ABOUT IT. IT NEVER CLEARS, AUTHORIZES, APPROVES, SIGNS,
    MINTS, STORES OR DECIDES.

Contracts only, under ``docs/architecture/ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md``
§10 and §13: a record type, three one-member enums, refusal reasons, pure
selectors, one read-only Protocol and one pure verifier. **No store, no adapter,
no connector, no clock and no network** — nothing here could reach a clearance
evaluator, a policy, a key or a runtime, so the lines the rulings draw are held
structurally rather than by discipline.

* CE-1 ``RECEIVED_CLEARANCE_ONLY`` — the artifact carries a ``ClearanceReceiptBody``
  the deployment received. A compile result establishes what was compiled; a
  clearance establishes whether a consequential action may proceed now and until
  when. :func:`build_export` accepts only the receipt type, and the reconstruction
  path refuses compile-shaped keys outright.
* CE-2 ``NEW_CONTRACTS_ONLY_PACKAGE`` — this package. ``action-clearance`` is not
  extended: its receipt body is re-serialized here and gains no field, no
  serialization concern and no transport concern from being exported.
* CE-3 ``ONE_MEMBER_NOW`` — :class:`IdentityAssurance` has the single member
  ``PRESENTED_UNPROVEN``, on the ``SystemBindingAuthenticityStatus`` precedent.
* CE-4 ``INTEGRITY_ONLY_AND_SAY_SO`` — :class:`ExportAuthenticity` is ``UNSIGNED``,
  the unfed prerequisite is named in the artifact itself, and
  :func:`verify_export` returns a report rather than a boolean so integrity is
  never read as authenticity.
* CE-5 ``EXPORT_IS_A_READ`` — :class:`ReceivedClearanceSource` has two reads and no
  write. There is no method here that accepts a receipt.
* CE-7 / §13.1 — :class:`ExportDataClassification` is
  ``SYNTHETIC_DEMONSTRATION_ONLY``. A seeded receipt exercises the export path and
  the verifier and is evidence about nothing else.

**The three honesty labels are required, validated and fingerprinted.** They are
keyword arguments with one admissible value each, not defaults; they are always
serialized; and they sit inside the fingerprint preimage, so stripping one is
detected exactly as an altered decision is detected. An artifact cannot be built
that omits them, and cannot be rebuilt from a payload that dropped them.

An export is a copy of a record. Making one changes nothing about what the record
means, and confers nothing on whoever holds it.
"""

from __future__ import annotations

from ugence_action_clearance import ClearanceReceiptBody, ClearanceStatus

from .artifact import (
    ARTIFACT_ID_PREFIX,
    AUTHENTICITY_PREREQUISITE,
    COMPILE_SHAPED_KEYS,
    ClearanceExportArtifact,
    ExportAuthenticity,
    ExportDataClassification,
    IdentityAssurance,
    artifact_from_dict,
    artifact_to_dict,
    build_export,
    canonical_form,
    receipt_body_from_dict,
    receipt_body_to_dict,
)
from .errors import (
    AuthenticityClaimRefused,
    ClassificationClaimRefused,
    ClearanceExportError,
    ContractViolation,
    ExportIntegrityError,
    IdentityAssuranceClaimRefused,
    NotAReceivedClearance,
)
from .selectors import (
    ReceivedClearanceSource,
    select_by_receipt_id,
    select_for_tenant,
)
from .verifier import UNCHECKABLE, ExportVerification, verify_export
from .version import (
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    MATURITY,
    __version__,
)

__all__ = [
    # identity and posture
    "__version__",
    "CONTRACT_VERSION",
    "MATURITY",
    "ENFORCEMENT_ENABLED",
    # the artifact
    "ARTIFACT_ID_PREFIX",
    "AUTHENTICITY_PREREQUISITE",
    "COMPILE_SHAPED_KEYS",
    "ClearanceExportArtifact",
    "build_export",
    "artifact_to_dict",
    "artifact_from_dict",
    "canonical_form",
    "receipt_body_to_dict",
    "receipt_body_from_dict",
    # the three honesty labels
    "IdentityAssurance",
    "ExportAuthenticity",
    "ExportDataClassification",
    # the verifier
    "verify_export",
    "ExportVerification",
    "UNCHECKABLE",
    # the one read-only port, and pure selectors over what it returns
    "ReceivedClearanceSource",
    "select_by_receipt_id",
    "select_for_tenant",
    # re-exported, never redefined
    "ClearanceReceiptBody",
    "ClearanceStatus",
    # refusals
    "ClearanceExportError",
    "ContractViolation",
    "ExportIntegrityError",
    "AuthenticityClaimRefused",
    "IdentityAssuranceClaimRefused",
    "ClassificationClaimRefused",
    "NotAReceivedClearance",
]
