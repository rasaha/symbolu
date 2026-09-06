"""Structural validation of the authoritative-source linkage (PA/PWC-X1).

**This module checks carriage, not authenticity.** It verifies that an
:class:`AuthoritativeSourceRef` is present where required, well-formed, complete,
and internally consistent with the release that carries it. It never verifies a
signature, never establishes key trust, and never consults revocation state — the
compiler imports nothing from Policy Authority and could not perform those checks
without becoming a second implementation of authority semantics.

The diagnostic vocabulary is deliberately split so no code here can be misread as
an authenticity claim:

===========================  ==========================================
this module asserts          Policy Authority asserts (never here)
===========================  ==========================================
the reference is present     the signature is valid
the coordinate is well-formed the key is trusted
the attestation is complete  the policy is not revoked
the release agrees with it   the resolution is current
===========================  ==========================================

``MISSING_AUTHORITATIVE_SOURCE`` is raised only when a caller states that it
requires the linkage. A ``policy_pack.v2`` pack is a schema, not an authority
integration: mandating Policy Authority linkage on every v2 pack would couple the
two, which the ratified boundary keeps apart. The composition root that derives the
reference from a ``RESOLVED`` resolution is the caller that requires it.
"""

from __future__ import annotations

from typing import List, Optional

from ..models.declarations import AuthoritativeSourceRef
from ..models.policy_pack import PolicyPack
from .errors import Severity, ValidationDiagnostic

#: Digest-shaped fields must carry this prefix; the compiler checks the shape only,
#: never whether the digest describes anything.
_DIGEST_PREFIX = "sha256:"

#: Coordinate fields that must all be present for the reference to identify one
#: exact issuance. ``tenant_id`` is excluded: Policy Authority itself defaults it.
_REQUIRED_COORDINATE_FIELDS = (
    "policy_family",
    "policy_id",
    "policy_version",
    "content_digest",
    "scope",
    "record_id",
    "policy_body_digest",
)

#: The issuance attestation is all-or-none, mirroring Policy Authority's own rule
#: for its descriptor triple: a partial attestation looks checkable and is not.
_ATTESTATION_FIELDS = (
    "issuing_authority_id",
    "key_id",
    "signature_alg",
    "signature_b64",
)


def _diag(code: str, severity: Severity, message: str, object_id: str,
          remediation: str) -> ValidationDiagnostic:
    return ValidationDiagnostic(
        code=code, severity=severity, message=message,
        object_id=object_id, suggested_remediation=remediation,
    )


def check_authoritative_source(
    pack: PolicyPack, *, required: bool = False
) -> List[ValidationDiagnostic]:
    """Validate the pack's authoritative-source linkage, structurally.

    Set ``required`` when the caller demands authoritative linkage — a composition
    root compiling from a resolved Policy Authority issuance always does.
    """
    out: List[ValidationDiagnostic] = []
    source: Optional[AuthoritativeSourceRef] = pack.authoritative_source

    if source is None:
        if required:
            out.append(
                _diag(
                    "MISSING_AUTHORITATIVE_SOURCE",
                    Severity.ERROR,
                    "authoritative source linkage is required for this compilation "
                    "but the pack carries none",
                    pack.pack_id,
                    "compile from a RESOLVED Policy Authority resolution through the "
                    "designated composition root",
                )
            )
        return out

    for field in _REQUIRED_COORDINATE_FIELDS:
        value = getattr(source, field, "")
        if not str(value).strip():
            out.append(
                _diag(
                    "MALFORMED_AUTHORITATIVE_COORDINATE",
                    Severity.ERROR,
                    f"authoritative source is missing '{field}'; the coordinate does "
                    f"not identify one exact issuance",
                    pack.pack_id,
                    "carry the complete coordinate from the resolved issuance record",
                )
            )
    for field in ("content_digest", "policy_body_digest"):
        value = str(getattr(source, field, ""))
        if value and not value.startswith(_DIGEST_PREFIX):
            out.append(
                _diag(
                    "MALFORMED_AUTHORITATIVE_COORDINATE",
                    Severity.ERROR,
                    f"authoritative source '{field}' is not a {_DIGEST_PREFIX}… digest",
                    pack.pack_id,
                    "carry the digest exactly as the issuance record states it",
                )
            )

    present = [bool(str(getattr(source, f, "")).strip()) for f in _ATTESTATION_FIELDS]
    if any(present) and not all(present):
        missing = [
            f for f, ok in zip(_ATTESTATION_FIELDS, present) if not ok
        ]
        out.append(
            _diag(
                "INCOMPLETE_ISSUANCE_ATTESTATION",
                Severity.ERROR,
                f"issuance attestation is partial (missing {', '.join(missing)}); a "
                f"partial attestation looks checkable and is not",
                pack.pack_id,
                "carry the whole attestation from the issuance record, or none of it",
            )
        )
    return out


def check_release_source_agreement(
    package_source: Optional[AuthoritativeSourceRef],
    manifest_coordinate: str,
    pack_id: str,
) -> List[ValidationDiagnostic]:
    """The manifest's denormalized coordinate must agree with the pack's reference.

    The manifest copy exists for offline inspection and is outside the logical
    digest, so it is the copy that can drift. Disagreement is an integrity failure
    of *this release* — not a statement about the issuance it names.
    """
    expected = coordinate_string(package_source)
    if manifest_coordinate == expected:
        return []
    return [
        _diag(
            "AUTHORITATIVE_SOURCE_MISMATCH",
            Severity.ERROR,
            f"release manifest coordinate {manifest_coordinate!r} does not match the "
            f"pack's authoritative source {expected!r}",
            pack_id,
            "rebuild the release so the manifest reflects the pack it contains",
        )
    ]


def coordinate_string(source: Optional[AuthoritativeSourceRef]) -> str:
    """The manifest's denormalized coordinate: a stable, inspectable identity.

    Empty when the pack carries no authoritative source. This is a rendering of the
    coordinate for offline reading — never a substitute for the reference itself.
    """
    if source is None:
        return ""
    return "/".join(
        (
            source.policy_family,
            source.policy_id,
            source.policy_version,
            source.scope,
            source.tenant_id or "-",
            source.content_digest,
        )
    )


__all__ = [
    "check_authoritative_source",
    "check_release_source_agreement",
    "coordinate_string",
]
