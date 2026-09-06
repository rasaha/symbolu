"""The immutable signed-comparison-result wrapper (SCR-1), and the payload it signs.

A :class:`SignedComparisonResult` binds one **complete** engine-produced
``ReadinessComparisonResult`` — held by exact type, never copied field by field
into a competing shape — together with the signer's identity, role, key
reference, algorithm, schema/domain version and signature. It adds, repairs and
reinterprets nothing: ``reasoning-method-governance`` is wrapped, not modified,
and the engine stays a pure function with no cryptography.

What is signed is the result's own identity: its schema, request identity and
digest, authority-resolution basis, engine identity and version, the instant it
was produced, and its ``result_digest`` — **recomputed** through the governance
contract from the wrapped object every time it is read, never copied from the
field. A result whose stored digest disagrees with its recomputed one is
refused at wrap time. Because ``result_digest`` is a function of the request
alone (it excludes ``produced_at`` and takes each assessment's time-free
payload), signing it binds the comparison's content; the projection also binds
the instant, so the same content produced twice is two signed statements.

Under the ``COMPARISON_ENGINE`` role the signer *is* the engine the result
names: a wrapper whose ``signer_identity`` differs from the result's
``engine_identity`` is a contract refusal, not a verification refusal.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from ugence_reasoning_method_governance.api import ReadinessComparisonResult

from .canonical import (
    canonical_digest,
    framed_signing_bytes,
    require_aware_utc,
    require_canonical_identifier,
    require_exact_type,
    require_nfc_text,
)
from .errors import ComparisonResultAttestationContractError as _Error
from .identifiers import (
    COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE,
    COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN,
)
from .roles import ComparisonResultAttesterRole, require_role

__all__ = [
    "SignedComparisonResult",
    "canonical_comparison_result",
    "comparison_result_digest",
    "comparison_result_signing_payload",
    "comparison_result_signing_bytes",
    "COMPARISON_RESULT_SIGNED_FIELDS",
    "COMPARISON_RESULT_PROJECTED_FIELDS",
]

#: The fields the signature covers, in canonical (sorted) key order, stated once
#: so a reader and a test can see that ``signature`` itself is not among them.
COMPARISON_RESULT_SIGNED_FIELDS: Final[tuple] = (
    "result",
    "result_digest",
    "schema_version",
    "signature_algorithm",
    "signature_encoding",
    "signature_profile",
    "signed_at",
    "signer_identity",
    "signer_key_id",
    "signer_role",
    "signing_domain",
)

#: The fields of the wrapped result that the canonical projection carries, in
#: sorted order. Every one is a string on the governance contract except
#: ``produced_at`` (an aware instant) and ``result_digest`` (recomputed).
COMPARISON_RESULT_PROJECTED_FIELDS: Final[tuple] = (
    "authority_resolution_basis",
    "engine_identity",
    "engine_version",
    "produced_at",
    "request_digest",
    "request_id",
    "result_digest",
    "schema_version",
)

_SIGNATURE_HEX_LENGTH: Final[int] = 128
_HEX_ALPHABET: Final[frozenset] = frozenset("0123456789abcdef")
_GOVERNANCE_DIGEST_LENGTH: Final[int] = 64


def _require_governance_digest(name: str, value: object) -> str:
    """The governance contract spells its digests as bare 64-hex; this package
    carries that value verbatim, never relabelled, because it is the value the
    advisor's admission cites."""

    text = require_nfc_text(name, value)
    if len(text) != _GOVERNANCE_DIGEST_LENGTH or not set(text) <= _HEX_ALPHABET:
        raise _Error(f"{name} must be the governance contract's bare 64-lowercase-hex digest")
    return text


def recomputed_result_digest(result: ReadinessComparisonResult) -> str:
    """The wrapped result's ``result_digest``, recomputed through the governance
    contract from the object's own fields, and required to equal the stored one.

    ``dataclasses.replace`` with an empty digest re-runs the contract's own
    settlement; nothing here re-implements the governance canonicalization.
    """

    require_exact_type("result", result, ReadinessComparisonResult)
    stored = _require_governance_digest("result.result_digest", result.result_digest)
    recomputed = dataclasses.replace(result, result_digest="").result_digest
    if recomputed != stored:
        raise _Error(
            "result.result_digest does not equal the digest recomputed from the result's "
            "own fields; a result whose self-digest was altered after construction is refused"
        )
    return stored


def canonical_comparison_result(result: ReadinessComparisonResult) -> dict:
    """The canonical projection of one exact ``ReadinessComparisonResult``.

    The result's identity fields as NFC text, ``produced_at`` as an aware
    instant, and ``result_digest`` recomputed. Nothing is added, dropped from
    the identity, or reinterpreted; the assessments, refusals, evidence-status
    views and ignored envelopes are bound through ``result_digest``, which the
    governance contract computes over them.
    """

    require_exact_type("result", result, ReadinessComparisonResult)
    return {
        "authority_resolution_basis": require_canonical_identifier(
            "result.authority_resolution_basis", result.authority_resolution_basis
        ),
        "engine_identity": require_canonical_identifier("result.engine_identity", result.engine_identity),
        "engine_version": require_canonical_identifier("result.engine_version", result.engine_version),
        "produced_at": require_aware_utc("result.produced_at", result.produced_at),
        "request_digest": _require_governance_digest("result.request_digest", result.request_digest),
        "request_id": require_canonical_identifier("result.request_id", result.request_id),
        "result_digest": recomputed_result_digest(result),
        "schema_version": require_canonical_identifier("result.schema_version", result.schema_version),
    }


def comparison_result_digest(result: ReadinessComparisonResult) -> str:
    """``sha256:`` digest of :func:`canonical_comparison_result` — this package's
    digest of the complete projection, distinct from the governance contract's
    bare-hex ``result_digest`` that the projection carries."""

    return canonical_digest(canonical_comparison_result(result))


def comparison_result_signing_payload(
    *,
    result: ReadinessComparisonResult,
    signer_role: ComparisonResultAttesterRole,
    signer_identity: str,
    signer_key_id: str,
    signed_at: datetime,
    schema_version: str = COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION,
    signing_domain: str = COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN,
    signature_algorithm: str = COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM,
    signature_profile: str = COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE,
    signature_encoding: str = COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING,
) -> dict:
    """The exact canonical object a signer signs and a verifier recomputes.

    Built from the arguments **only**. The verifier calls this with the result
    *it* holds and the metadata the signed result claims, so a substituted
    result or a lifted signature differs in bytes before it differs in anything
    else. Under the ``COMPARISON_ENGINE`` role the signer identity must be the
    result's own ``engine_identity``.
    """

    canonical = canonical_comparison_result(result)
    role = require_role("signer_role", signer_role)
    identity = require_canonical_identifier("signer_identity", signer_identity)
    if role is ComparisonResultAttesterRole.COMPARISON_ENGINE and identity != canonical["engine_identity"]:
        raise _Error(
            "under the COMPARISON_ENGINE role the signer_identity must equal the result's "
            f"engine_identity ({canonical['engine_identity']!r}); a signer speaking for another "
            "identity cannot sign this result as its engine"
        )
    return {
        "result": canonical,
        "result_digest": canonical["result_digest"],
        "schema_version": require_canonical_identifier("schema_version", schema_version),
        "signature_algorithm": require_canonical_identifier("signature_algorithm", signature_algorithm),
        "signature_encoding": require_canonical_identifier("signature_encoding", signature_encoding),
        "signature_profile": require_canonical_identifier("signature_profile", signature_profile),
        "signed_at": require_aware_utc("signed_at", signed_at),
        "signer_identity": identity,
        "signer_key_id": require_canonical_identifier("signer_key_id", signer_key_id),
        "signer_role": role.value,
        "signing_domain": require_canonical_identifier("signing_domain", signing_domain),
    }


def comparison_result_signing_bytes(payload: dict) -> bytes:
    """The framed bytes that are actually signed: domain prefix, then payload."""

    require_exact_type("payload", payload, dict)
    return framed_signing_bytes(payload["signing_domain"], payload)


def _require_signature_encoding(name: str, value: object) -> str:
    text = require_nfc_text(name, value)
    if len(text) != _SIGNATURE_HEX_LENGTH or not set(text) <= _HEX_ALPHABET:
        raise _Error(
            f"{name} must be exactly {_SIGNATURE_HEX_LENGTH} lowercase hex characters "
            "(64 bytes); uppercase, prefixed, padded, short and long spellings are refused"
        )
    return text


@dataclass(frozen=True)
class SignedComparisonResult:
    """One signed statement by one signer, under one role, about one comparison result.

    Immutable, exact-typed, and self-describing: every identifier that decides
    how it is verified is a field here and inside the signed bytes. It does
    **not** carry the anchor, the public key, a verification outcome, an
    admission, or any claim about whether the comparison is correct.
    """

    #: The complete wrapped result. Exact type; never a look-alike.
    result: ReadinessComparisonResult
    #: Under which role the signer signs (SCR-1). Signed and coordinate-bound.
    signer_role: ComparisonResultAttesterRole
    #: The signer's identity — the anchor's ``authority_id``. Under the engine
    #: role, the result's own ``engine_identity``.
    signer_identity: str
    #: The signer's key reference — the anchor's ``key_id``.
    signer_key_id: str
    #: When the signer says it signed. Caller-supplied; never a clock read here.
    signed_at: datetime
    #: The detached signature, exactly 128 lowercase hex characters.
    signature: str
    #: Contract identifiers, all pinned and all signed.
    schema_version: str = COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION
    signing_domain: str = COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN
    signature_algorithm: str = COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM
    signature_profile: str = COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE
    signature_encoding: str = COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING

    def __post_init__(self) -> None:
        # Building the payload validates every field, including the wrapped
        # result's recomputed digest, without storing anything derived.
        self.signing_payload()
        _require_signature_encoding("signature", self.signature)

    def signing_payload(self) -> dict:
        """The canonical payload, rebuilt from this object's fields every time."""

        return comparison_result_signing_payload(
            result=self.result,
            signer_role=self.signer_role,
            signer_identity=self.signer_identity,
            signer_key_id=self.signer_key_id,
            signed_at=self.signed_at,
            schema_version=self.schema_version,
            signing_domain=self.signing_domain,
            signature_algorithm=self.signature_algorithm,
            signature_profile=self.signature_profile,
            signature_encoding=self.signature_encoding,
        )

    def signed_bytes(self) -> bytes:
        """The framed bytes this signed result claims were signed."""

        return comparison_result_signing_bytes(self.signing_payload())

    @property
    def result_digest(self) -> str:
        """The governance contract's ``result_digest``, recomputed from the
        wrapped result; never stored here. Bare hex, as the contract spells it."""

        return recomputed_result_digest(self.result)

    @property
    def comparison_result_digest(self) -> str:
        """This package's ``sha256:`` digest of the complete projection; never stored."""

        return comparison_result_digest(self.result)

    @property
    def signing_payload_digest(self) -> str:
        """Recomputed from the payload; never stored."""

        return canonical_digest(self.signing_payload())
