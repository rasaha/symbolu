"""The receipt-signing boundary — narrow by construction, not by convention.

ADR §30 assigns "signing" to TEV-2, and §8 role 4 assigns receipt issuance to
"**TAP**, under a configured authority key". This module is that boundary, and
it is deliberately the narrowest surface in the package.

There is no "sign arbitrary bytes" capability
---------------------------------------------
The obvious shape for a signer port is ``sign(payload: bytes) -> bytes``. It is
not the shape used here, because it is a public oracle: anything a caller can
serialize, a configured signer would sign, and a signature is only worth
anything if the set of things it can cover is closed.

Instead a signer receives a :class:`ReceiptSigningInput` — a token-guarded,
package-constructed value object. There is exactly one way to obtain one:

    verify evidence  ->  an ADMITTED determination  ->  issue  ->  signature

:class:`ReceiptIssuer` mints the signing input, and it mints one **only** from
an :class:`~.verification.EvidenceVerificationDetermination` that carries the
private issuance token the verification authority stamps into an admitted
determination. A caller cannot construct that token, cannot construct an
admitted determination without it, and therefore cannot reach a signature over
bytes of their choosing. A caller-set ``admitted=True`` is not merely
disbelieved — it is unrepresentable.

What this does *not* claim
--------------------------
A determined adversary executing inside this process can import a private module
attribute, and no Python-level mechanism prevents that; the same is true of the
merged Policy Authority and Risk Authority signers. The token closes the
**public API** route, which is what it is for. The load-bearing secret remains
the signing key, which lives only behind this port and never enters a contract,
a digest, a canonical byte sequence, a ``repr``, an exception message or an
audit record.

Signing is not verifying
------------------------
A signature produced here proves only that the holder of a key signed a frame.
Whether that key was trusted, entitled, in-window and unrevoked is a **separate**
question answered by :class:`~.reverification.SignedReceiptVerifier` against a
resolved trust anchor. ADR §10.5 and §13.3 are explicit that a structurally
valid receipt whose key or trust anchor did not verify is not a receipt, so this
module never reports success — it returns bytes, and something else decides.

Production key custody stays behind the port (DD-10)
----------------------------------------------------
:class:`Ed25519ReceiptSigner` is the reference implementation. An HSM- or
KMS-backed signer implements the same :class:`ReceiptSignerPort` and drops in
without touching a caller. TEV-2 adds **no** environment-variable key loading,
**no** filesystem key discovery, **no** network KMS and **no** secret
persistence: ``os``, ``pathlib``, ``socket`` and ``secrets`` are all banned
package-wide, and a structural test enforces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..contracts._validation import require_exact_type, require_identifier
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .backend import TrustedEvidenceSigningKey
from .profile import (
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    encode_public_key,
    encode_signature,
)
from .trust import TrustAnchorCapability, TrustAnchorRecord

__all__ = [
    "ReceiptSigningInput",
    "ReceiptSignerPort",
    "Ed25519ReceiptSigner",
]

_R = TrustedEvidenceRefusalReason

#: The private capability token. Not exported, not in ``__all__``, not reachable
#: from the curated API. Holding it is what distinguishes a signing input the
#: package built from one a caller assembled.
_SIGNING_INPUT_TOKEN = object()


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


@dataclass(frozen=True)
class ReceiptSigningInput:
    """A package-minted instruction to sign one specific receipt frame.

    Not a contract: it carries ``bytes``, which the canonical encoder rejects,
    so it can never be canonicalized, digested, stored in an artifact or
    serialized into anything. It exists only to travel from
    :class:`~.issuance.ReceiptIssuer` to a :class:`ReceiptSignerPort` and be
    discarded.

    Direct construction is refused. The ``issuance_token`` argument must be the
    package's private token, which the curated API does not export and a caller
    has no supported route to; passing ``None``, ``True``, a look-alike sentinel,
    a string or any other object raises. This is what makes "sign these bytes"
    unreachable from outside.
    """

    signed_input: bytes
    signer_authority_id: str
    signing_key_id: str
    signature_profile: str
    issuance_token: object = None

    def __post_init__(self) -> None:
        if self.issuance_token is not _SIGNING_INPUT_TOKEN:
            raise _fail(
                "ReceiptSigningInput cannot be constructed directly. A signing "
                "input is minted only by ReceiptIssuer, and only from an "
                "EvidenceVerificationDetermination that the verification "
                "authority admitted — there is no supported route from "
                "caller-chosen bytes to an authority signature (ADR E-3, E-5, "
                "§8.1.5: 'no consumer may manufacture verification')",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if type(self.signed_input) is not bytes:
            raise _fail(
                "ReceiptSigningInput.signed_input must be exactly bytes "
                f"(got {type(self.signed_input).__name__})",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if len(self.signed_input) == 0:
            raise _fail(
                "ReceiptSigningInput.signed_input must not be empty; a signature "
                "over nothing covers nothing",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        require_identifier(
            self.signer_authority_id, "ReceiptSigningInput.signer_authority_id"
        )
        require_identifier(self.signing_key_id, "ReceiptSigningInput.signing_key_id")
        if self.signature_profile != TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1:
            raise _fail(
                "ReceiptSigningInput.signature_profile must be exactly "
                f"{TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1!r}",
                _R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED,
            )

    def __repr__(self) -> str:
        """Byte length only. The frame itself is not rendered into logs."""

        return (
            "ReceiptSigningInput(authority="
            f"{self.signer_authority_id!r}, key={self.signing_key_id!r}, "
            f"{len(self.signed_input)} bytes)"
        )


@runtime_checkable
class ReceiptSignerPort(Protocol):
    """Produce the authority's signature over a package-minted receipt frame.

    The signer names the authority and key it speaks for, so
    :class:`~.issuance.ReceiptIssuer` can bind those coordinates into the frame
    *before* signing rather than trusting the signer to have signed what it
    says. An implementation that signs under a different key than it advertises
    produces a signature that will not verify against the advertised
    coordinate's trust anchor — which is a refusal, not a silent success.
    """

    @property
    def signer_authority_id(self) -> str:
        """The authority identity this signer speaks for (ADR §9 row 14)."""
        ...

    @property
    def signing_key_id(self) -> str:
        """The exact key identifier a verifier will resolve (ADR §9 row 14)."""
        ...

    @property
    def signature_profile(self) -> str:
        """The one ratified profile. There is no second value to return."""
        ...

    def sign_receipt(self, signing_input: ReceiptSigningInput) -> str:
        """Return the signature, in the one canonical encoding."""
        ...


class Ed25519ReceiptSigner:
    """The reference :class:`ReceiptSignerPort` over the RFC 8032 implementation.

    Holds a :class:`~.backend.TrustedEvidenceSigningKey` and nothing else, and
    that key holds only a backend private-key object — never the caller's raw
    seed bytes (closure-audit **F-08**). There is no accessor that returns
    private material from either object, and neither can be pickled or copied.

    Not a dataclass, and not frozen-by-decorator but frozen-by-refusal:
    ``__setattr__`` raises after construction, so a signing key cannot be
    swapped out from under a configured issuer.
    """

    __slots__ = ("_signer_authority_id", "_signing_key_id", "_signing_key")

    def __init__(
        self,
        *,
        signer_authority_id: str,
        signing_key_id: str,
        signing_key: TrustedEvidenceSigningKey,
    ) -> None:
        require_identifier(
            signer_authority_id, "Ed25519ReceiptSigner.signer_authority_id"
        )
        require_identifier(signing_key_id, "Ed25519ReceiptSigner.signing_key_id")
        require_exact_type(
            signing_key,
            TrustedEvidenceSigningKey,
            "Ed25519ReceiptSigner.signing_key",
        )
        object.__setattr__(self, "_signer_authority_id", signer_authority_id)
        object.__setattr__(self, "_signing_key_id", signing_key_id)
        object.__setattr__(self, "_signing_key", signing_key)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"Ed25519ReceiptSigner is immutable; cannot set {name!r}. Rebinding "
            "the signing key or its advertised coordinates after configuration "
            "would let a caller re-point an already-trusted signer."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"Ed25519ReceiptSigner is immutable; cannot delete {name!r}")

    @property
    def signer_authority_id(self) -> str:
        return self._signer_authority_id

    @property
    def signing_key_id(self) -> str:
        return self._signing_key_id

    @property
    def signature_profile(self) -> str:
        return TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1

    def sign_receipt(self, signing_input: ReceiptSigningInput) -> str:
        """Sign the package-minted frame, returning canonical lowercase hex.

        Refuses a signing input addressed to a different authority or key than
        this signer holds: a signer must never produce a signature labelled with
        coordinates it cannot answer for, because a verifier would then resolve
        the *labelled* anchor and check a signature made by a different key.
        """

        require_exact_type(
            signing_input, ReceiptSigningInput, "Ed25519ReceiptSigner.signing_input"
        )
        if signing_input.signer_authority_id != self._signer_authority_id:
            raise _fail(
                "Ed25519ReceiptSigner refuses a signing input addressed to "
                f"authority {signing_input.signer_authority_id!r}; this signer "
                f"speaks for {self._signer_authority_id!r}",
                _R.TRUSTED_EVIDENCE_AUTHORITY_MISMATCH,
            )
        if signing_input.signing_key_id != self._signing_key_id:
            raise _fail(
                "Ed25519ReceiptSigner refuses a signing input addressed to key "
                f"{signing_input.signing_key_id!r}; this signer holds "
                f"{self._signing_key_id!r}",
                _R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH,
            )
        return encode_signature(self._signing_key.sign(signing_input.signed_input))

    def trust_anchor(
        self,
        *,
        trust_anchor_set_id: str,
        trust_anchor_set_version: str,
        effective_from=None,
        effective_to=None,
    ) -> TrustAnchorRecord:
        """Publish this signer's **public** half for registration as an anchor.

        A convenience for a composition root wiring a reference deployment, and
        for tests. The result carries only public material, and it is always
        minted with :attr:`~.trust.TrustAnchorCapability.RECEIPT_ISSUANCE` — a
        receipt signer cannot publish itself as an evidence producer, which is
        ADR E-3's producer/verifier separation holding at the one place where a
        key's public half is derived from its private half.

        Publishing an anchor is a *configuration* act, not an authorization one:
        registering the returned record into a directory is the composition
        root's decision (E-5), and this method neither performs nor implies it.
        """

        return TrustAnchorRecord(
            authority_id=self._signer_authority_id,
            key_id=self._signing_key_id,
            capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
            public_key=encode_public_key(
                self._signing_key.verification_key.public_key_bytes
            ),
            trust_anchor_set_id=trust_anchor_set_id,
            trust_anchor_set_version=trust_anchor_set_version,
            effective_from=effective_from,
            effective_to=effective_to,
        )

    def __repr__(self) -> str:
        """Coordinates only. The key is never rendered."""

        return (
            "Ed25519ReceiptSigner(authority="
            f"{self._signer_authority_id!r}, key={self._signing_key_id!r})"
        )
