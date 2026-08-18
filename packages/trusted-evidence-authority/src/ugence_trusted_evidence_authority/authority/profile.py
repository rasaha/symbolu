"""The single strict TEV-2 cryptographic profile, and its signed-byte framing.

ADR §13.3 ratifies *that* domain tags, algorithm identifiers and encodings must
be "unambiguous, versioned, and fixed before signing exists", and **DD-9
explicitly delegates the exact byte constants to TEV-1/TEV-2**. TEV-1 discharged
the digest half (canonicalization version, evidence-identity domain,
receipt-payload domain). This module discharges the signature half.

One profile, no negotiation
---------------------------
There is exactly **one** signature profile, and it is not selectable:

* algorithm — **Ed25519** (RFC 8032, PureEdDSA over edwards25519 with SHA-512);
* signature encoding — **lowercase base16**, 128 characters for the 64 signature
  bytes;
* public-key encoding — **lowercase base16**, 64 characters for the 32 key bytes.

There is no ``none`` algorithm, no alias, no permissive fallback, no
caller-selected algorithm, no negotiation and no downgrade path. Every contract
that names a profile validates it against :data:`TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1`
by exact string equality; an unsupported profile is
``TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED``, which is a refusal (§22.8 —
"an unrecognized … algorithm identifier is a refusal, never a best-effort
serialization"). ADR §26 offers no ratified need for algorithm agility, so
none is built: a menu of algorithms is a menu of downgrade attacks.

Why base16 and not base64
-------------------------
A byte string has exactly one lowercase-base16 spelling, and TEV-1 already uses
bare lowercase hex for every digest, so one encoding rule covers the package.
Base64 does not have that property: the trailing bits of a final quantum are
unconstrained by most decoders, so several distinct base64 strings decode to the
same bytes. That would let an attacker mint a *different* envelope carrying the
*same* signature, changing the envelope digest without touching the signature —
a substitution route this encoding closes by construction. Uppercase hex, a
``0x`` prefix, whitespace, and any non-hex character are refused rather than
normalized, matching the package-wide "reject, never silently repair" posture.

Signed-byte construction — length-prefixed, never concatenated prose
--------------------------------------------------------------------
Signing ``a + b`` is ambiguous: ``("ab", "c")`` and ``("a", "bc")`` produce the
same bytes, so a signature over one can be reinterpreted as a signature over the
other. Every signed input here is therefore a **length-prefixed frame**:

    frame = count(8 bytes, big-endian)
            ‖ for each element: length(8 bytes, big-endian) ‖ element bytes

The element count is bound first, so a frame cannot be extended or truncated
into a different valid frame, and no element boundary can be moved. The frame is
a pure function of its elements, contains no separator that an element could
impersonate, and is trivially reconstructible by a third party holding nothing
but this module's documented rules.

Two signing domains, never interchangeable
------------------------------------------
ADR §26.6 requires that "a receipt signature must not verify as a benchmark
signature or a policy signature", and §13.3 that "a signature valid in one
domain must not verify in another". TEV-2 signs two different artifact classes
and gives each its own domain tag, bound as the **first** element of its frame:

* :data:`TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN` — a producer's signature
  over an evidence item, which establishes ADR §12 **stage 2**;
* :data:`TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN` — the verifying
  authority's signature over a receipt payload, which is the ADR E-11 receipt.

Because the domain is the first framed element and the frame binds its own
element count, an evidence signature can never verify as a receipt signature
even under the same key — and ADR §8.1.1's rule that "an evidence producer
cannot verify its own evidence" is additionally enforced structurally by
:class:`~.trust.TrustAnchorCapability`, so the same key cannot hold both roles.
"""

from __future__ import annotations

__all__ = [
    "TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1",
    "TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1",
    "TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN",
    "TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN",
    "SIGNED_INPUT_LENGTH_PREFIX_BYTES",
    "encode_signature",
    "decode_signature",
    "encode_public_key",
    "decode_public_key",
    "framed_signed_input",
]

from ..contracts._validation import require_canonical_str
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .backend import ED25519_PUBLIC_KEY_SIZE, ED25519_SIGNATURE_SIZE

#: The one ratified TEV-2 signature profile (DD-9). Exact-match only.
#:
#: Names the algorithm, its hash and its edition together, so a future profile
#: is a *different string* rather than a reinterpretation of this one.
TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1 = (
    "ugence.trusted-evidence-authority/signature/ed25519-sha512-pure/v1"
)

#: The one ratified encoding for signature and public-key bytes (DD-9).
TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1 = (
    "ugence.trusted-evidence-authority/encoding/base16-lower/v1"
)

#: Domain tag bound as element 0 of a producer's evidence signature (§12 stage 2).
TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN = (
    "ugence.trusted-evidence-authority/signed-evidence-input/v1"
)

#: Domain tag bound as element 0 of an authority's receipt signature (E-11).
TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN = (
    "ugence.trusted-evidence-authority/signed-receipt-input/v1"
)

#: Width of every length prefix in a signed-input frame, in bytes.
SIGNED_INPUT_LENGTH_PREFIX_BYTES = 8

_HEX_DIGITS = frozenset("0123456789abcdef")


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


def encode_signature(signature_bytes: bytes) -> str:
    """Encode Ed25519 signature bytes as the one canonical 128-char hex string."""

    if type(signature_bytes) is not bytes:
        raise _fail(
            "signature bytes must be exactly bytes "
            f"(got {type(signature_bytes).__name__})",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        )
    if len(signature_bytes) != ED25519_SIGNATURE_SIZE:
        raise _fail(
            f"an Ed25519 signature is {ED25519_SIGNATURE_SIZE} bytes, got "
            f"{len(signature_bytes)}; truncated and extended signatures are "
            "refused, never padded or trimmed",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        )
    return signature_bytes.hex()


def decode_signature(signature: object, name: str = "signature") -> bytes:
    """Decode the canonical hex spelling of an Ed25519 signature.

    Refuses uppercase, ``0x``-prefixed, padded, short, long and non-hex input
    rather than repairing it: a second accepted spelling of one signature would
    be a second envelope carrying one signature, which is exactly the
    substitution route the single encoding closes.
    """

    text = _require_lower_hex(
        signature, name, ED25519_SIGNATURE_SIZE, "Ed25519 signature"
    )
    return bytes.fromhex(text)


def encode_public_key(public_key_bytes: bytes) -> str:
    """Encode Ed25519 public-key bytes as the one canonical 64-char hex string."""

    if type(public_key_bytes) is not bytes:
        raise _fail(
            "public-key bytes must be exactly bytes "
            f"(got {type(public_key_bytes).__name__})",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        )
    if len(public_key_bytes) != ED25519_PUBLIC_KEY_SIZE:
        raise _fail(
            f"an Ed25519 public key is {ED25519_PUBLIC_KEY_SIZE} bytes, got "
            f"{len(public_key_bytes)}",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        )
    return public_key_bytes.hex()


def decode_public_key(public_key: object, name: str = "public_key") -> bytes:
    """Decode the canonical hex spelling of an Ed25519 public key."""

    text = _require_lower_hex(
        public_key, name, ED25519_PUBLIC_KEY_SIZE, "Ed25519 public key"
    )
    return bytes.fromhex(text)


def _require_lower_hex(value: object, name: str, byte_length: int, label: str) -> str:
    text = require_canonical_str(value, name, allow_empty=False)
    expected = byte_length * 2
    if len(text) != expected:
        raise _fail(
            f"{name} must be exactly {expected} lowercase hex characters for a "
            f"{label} ({byte_length} bytes), got {len(text)}",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        )
    if not _HEX_DIGITS.issuperset(text):
        raise _fail(
            f"{name} must be bare lowercase base16 under "
            f"{TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1}; uppercase, a '0x' "
            "prefix, whitespace, base64 and every other spelling are refused "
            "rather than normalized, so one byte string has one encoding",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID,
        )
    return text


def framed_signed_input(elements: tuple) -> bytes:
    """Build the length-prefixed, unambiguous byte frame described above.

    ``elements`` is an ordered tuple of ``bytes``. The element **count** is
    bound first, then each element is preceded by its own big-endian length, so
    no element boundary can be moved and no frame can be extended or truncated
    into another valid frame. There is no separator byte, so no element can
    impersonate one.

    Pure, total, and reconstructible by anyone holding the documented rules —
    which is what ADR §13.3 means by "a third party holding the receipt and the
    public verification functions can recompute the digest and check the
    signature without authority internals".
    """

    if type(elements) is not tuple:
        raise TrustedEvidenceContractError(
            "framed_signed_input expects a tuple of byte strings "
            f"(got {type(elements).__name__})"
        )
    if len(elements) == 0:
        raise TrustedEvidenceContractError(
            "framed_signed_input requires at least one element; an empty frame "
            "would be a signature over nothing"
        )
    width = SIGNED_INPUT_LENGTH_PREFIX_BYTES
    parts = [len(elements).to_bytes(width, "big")]
    for index, element in enumerate(elements):
        if type(element) is not bytes:
            raise TrustedEvidenceContractError(
                f"framed_signed_input element {index} must be exactly bytes "
                f"(got {type(element).__name__}); a str would depend on an "
                "implicit encoding choice and is refused"
            )
        parts.append(len(element).to_bytes(width, "big"))
        parts.append(element)
    return b"".join(parts)
