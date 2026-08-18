"""Ed25519 through maintained backends. No cryptography is implemented here.

This module replaces an earlier in-package pure-Python RFC 8032 implementation
that the independent TEV-2 closure audit found unsafe. That implementation is
**deleted**, not deprecated: there is no fallback, no environment switch, no
feature flag, no import-failure path back to it, and no vendored copy of RFC
sample code anywhere in the runtime package.

Why the previous justification was wrong
----------------------------------------
The earlier module argued that ADR §23 forced a stdlib-only implementation.
**It does not.** §23 is the *consumer and dependency matrix* — it governs the
direction of dependencies **between Ugence packages** ("TAP may consume
``governance-contracts`` only; must never import Benchmark Registry, Policy
Authority, any engine, Risk Authority"). Every entry in it names a Ugence
component. It says nothing about maintained third-party cryptographic
primitives, and reading it as a prohibition on them was an overread.

Nor does the presence of reference RFC 8032 code elsewhere in this repository
authorize handwritten cryptography on a production path. That code carries its
own "reference implementation … not for production" caveat; reproducing the
convention reproduced the caveat too.

What the audit actually found
-----------------------------
* **F-01** — the hand-rolled point decoder accepted the non-canonical encoding
  ``y=1`` with the sign bit set. RFC 8032 §5.1.3: "if x = 0 and x_0 = 1,
  decoding fails." That check was absent.
* **F-03** — a :class:`~.trust.TrustAnchorRecord` accepted an **identity**
  public key, and a signature forged for it (no private key required) drove the
  independent re-verifier all the way to ``VERIFIED``. A universal forgery.
* **F-06** — signing was secret-dependent Python: a measurable timing
  correlation with the private nonce's bit length.

Deleting the arithmetic is the architectural fix for all three.

The two backends, and why both
------------------------------
**Signing, key derivation and signature verification —** ``cryptography``
(:mod:`cryptography.hazmat.primitives.asymmetric.ed25519`), which wraps
OpenSSL. It provides Ed25519 key derivation from a seed, deterministic signing,
and strict verification with maintained constant-time secret handling. Binary
wheels are published for the repository's Python and platform matrix.

**Strict public-key point validation —** ``PyNaCl`` /libsodium's
:func:`crypto_core_ed25519_is_valid_point`. This is *not* redundant.
``cryptography``'s ``Ed25519PublicKey.from_public_bytes`` validates length and
defers everything else to verification time, so it cannot answer "is this key
safe to install as a trust anchor?" libsodium's primitive can: it returns true
only for a point that is on the curve, **in canonical form**, **on the main
subgroup**, and **not of small order** — exactly the properties F-01 and F-03
turn on. It is a maintained primitive, not reconstructed curve arithmetic.

An anchor is validated **at construction**, so a malformed, non-canonical,
identity or small-order key can never enter the anchor store at all. A later
failed signature check is not a substitute for that and is not claimed to be.

Availability is not optional
----------------------------
If either backend is missing, importing this package raises. There is no
degraded mode: a trusted-evidence verifier that silently loses strict point
validation, or falls back to unvetted arithmetic, would be worse than one that
refuses to start.
"""

from __future__ import annotations



__all__ = [
    "ED25519_SEED_SIZE",
    "ED25519_PUBLIC_KEY_SIZE",
    "ED25519_SIGNATURE_SIZE",
    "TrustedEvidenceSigningKey",
    "TrustedEvidenceVerificationKey",
    "backend_versions",
]

#: Byte length of an Ed25519 private seed (RFC 8032 §5.1.5).
ED25519_SEED_SIZE = 32
#: Byte length of an Ed25519 public key (RFC 8032 §5.1.5).
ED25519_PUBLIC_KEY_SIZE = 32
#: Byte length of an Ed25519 signature (RFC 8032 §5.1.6).
ED25519_SIGNATURE_SIZE = 64


# --------------------------------------------------------------------------- #
# Backend imports — hard requirements, never optional
# --------------------------------------------------------------------------- #

try:
    from cryptography.exceptions import InvalidSignature as _InvalidSignature
    from cryptography.hazmat.primitives import serialization as _serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey as _Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey as _Ed25519PublicKey,
    )
except ImportError as exc:  # a hard failure: there is no fallback to fall back to
    raise ImportError(
        "ugence-trusted-evidence-authority requires the 'cryptography' "
        "distribution for Ed25519 signing and verification. It is a declared "
        "runtime dependency. There is deliberately no pure-Python fallback: a "
        "trusted-evidence verifier must not silently downgrade to unvetted "
        "cryptography."
    ) from exc

try:
    from nacl.bindings import crypto_core_ed25519_is_valid_point as _is_valid_point
except ImportError as exc:  # a hard failure: there is no fallback to fall back to
    raise ImportError(
        "ugence-trusted-evidence-authority requires the 'PyNaCl' distribution "
        "for strict Ed25519 point validation (libsodium "
        "crypto_core_ed25519_is_valid_point). It is a declared runtime "
        "dependency. Length validation alone is not a substitute: it would "
        "admit identity, small-order and non-canonical trust-anchor keys, "
        "which is closure-audit finding F-03."
    ) from exc


def backend_versions() -> tuple:
    """The maintained backends actually in use, for audit and CI reporting.

    Returned as an ordered tuple of ``(distribution, version)`` pairs so a
    verification run can record exactly which vetted implementations produced
    its results.
    """

    import cryptography as _cryptography
    import nacl as _nacl

    return (
        ("cryptography", _cryptography.__version__),
        ("pynacl", _nacl.__version__),
    )


def _require_exact_bytes(value: object, name: str, length: int) -> bytes:
    if type(value) is not bytes:
        raise ValueError(
            f"{name} must be exactly bytes (got {type(value).__name__})"
        )
    if len(value) != length:
        raise ValueError(f"{name} must be {length} bytes, got {len(value)}")
    return value


def require_valid_ed25519_point(public_key_bytes: object, name: str) -> bytes:
    """Strictly validate a public key, or raise.

    Accepts only a point that libsodium reports as on the curve, **canonically
    encoded**, **on the prime-order main subgroup**, and **not of small order**.
    That rejects, at minimum:

    * the identity point, canonical (``0100…00``) and non-canonical (``0100…80``);
    * every small-order / torsion encoding;
    * ``y >= p`` and other non-canonical field elements;
    * off-curve points;
    * all-zero and all-``ff`` keys.

    This is a maintained primitive. Nothing here reimplements curve arithmetic.
    """

    raw = _require_exact_bytes(public_key_bytes, name, ED25519_PUBLIC_KEY_SIZE)
    try:
        valid = _is_valid_point(raw)
    except Exception:
        # libsodium signals malformed input by exception for some encodings.
        valid = False
    if valid is not True:
        raise ValueError(
            f"{name} is not a valid Ed25519 public key: it must be on the "
            "curve, canonically encoded, on the prime-order main subgroup, and "
            "not of small order. Identity, torsion, non-canonical and "
            "off-curve encodings are refused here, at construction, so they "
            "can never enter a trust-anchor store (closure-audit F-01, F-03)."
        )
    return raw


class TrustedEvidenceSigningKey:
    """An Ed25519 private key held **only** as a backend key object.

    Deliberately **not** a dataclass and deliberately without a ``seed`` field.
    Closure-audit finding **F-08** was that the previous implementation exposed
    the raw seed as a public dataclass attribute, so it escaped through
    ``dataclasses.asdict``, ``copy.deepcopy`` and ``pickle``. Here:

    * the constructor accepts seed bytes and **does not retain them** — they go
      straight into the backend key object and the Python-level reference is
      dropped;
    * there is no ``.seed``, no accessor, no property and no closure returning
      private material;
    * ``__slots__`` prevents an instance ``__dict__``, so there is nothing for
      ``asdict`` or ``vars`` to walk;
    * pickling, copying and deep-copying **raise**, so raw material cannot be
      duplicated or serialized;
    * attribute assignment after construction raises;
    * ``repr``/``str`` are redacted.

    *Stated plainly rather than overclaimed:* the backend key object lives in a
    private slot, and in-process code that reaches into private slots is not
    defended against — no Python-level mechanism can. What is closed is every
    **public** and **accidental** route: serialization, copying, logging,
    tracebacks, canonical bytes, manifests and the curated API.
    """

    __slots__ = ("_backend_private_key",)

    def __init__(self, seed: bytes) -> None:
        _require_exact_bytes(seed, "TrustedEvidenceSigningKey seed", ED25519_SEED_SIZE)
        object.__setattr__(
            self,
            "_backend_private_key",
            _Ed25519PrivateKey.from_private_bytes(seed),
        )

    # -- no mutation, no duplication, no serialization --------------------- #

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "TrustedEvidenceSigningKey is immutable; a signing key may not be "
            "rebound after construction"
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError("TrustedEvidenceSigningKey is immutable")

    def __reduce__(self):
        raise TypeError(
            "TrustedEvidenceSigningKey cannot be pickled: serializing a "
            "signing key would copy private material out of the signing "
            "boundary (closure-audit F-08)"
        )

    def __copy__(self):
        raise TypeError("TrustedEvidenceSigningKey cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("TrustedEvidenceSigningKey cannot be deep-copied")

    def __repr__(self) -> str:
        return "TrustedEvidenceSigningKey(<redacted>)"

    def __str__(self) -> str:
        return "TrustedEvidenceSigningKey(<redacted>)"

    # -- the only two things it does --------------------------------------- #

    @property
    def verification_key(self) -> "TrustedEvidenceVerificationKey":
        """Publish the public half. Private material is not derivable from it."""

        raw = self._backend_private_key.public_key().public_bytes(
            _serialization.Encoding.Raw, _serialization.PublicFormat.Raw
        )
        return TrustedEvidenceVerificationKey(raw)

    def sign(self, message: bytes) -> bytes:
        """Deterministic Ed25519 signature, produced by the maintained backend.

        Reaching this method requires already holding the key, which only a
        signer at the composition root does. The package exposes no route by
        which a caller hands arbitrary bytes to a configured signer — see
        :class:`~.signing.ReceiptSigningInput`.
        """

        if type(message) is not bytes:
            raise ValueError("message to sign must be exactly bytes")
        return self._backend_private_key.sign(message)


class TrustedEvidenceVerificationKey:
    """An Ed25519 public key, **strictly validated at construction**.

    Construction refuses identity, small-order, non-canonical, off-curve and
    malformed encodings via libsodium's maintained point-validation primitive.
    That placement is the point: a key that cannot be trusted can never be
    installed as a trust anchor, rather than being caught (or not) later.
    """

    __slots__ = ("_public_key_bytes", "_backend_public_key")

    def __init__(self, public_key_bytes: bytes) -> None:
        raw = require_valid_ed25519_point(
            public_key_bytes, "TrustedEvidenceVerificationKey.public_key_bytes"
        )
        object.__setattr__(self, "_public_key_bytes", raw)
        object.__setattr__(
            self, "_backend_public_key", _Ed25519PublicKey.from_public_bytes(raw)
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("TrustedEvidenceVerificationKey is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("TrustedEvidenceVerificationKey is immutable")

    @property
    def public_key_bytes(self) -> bytes:
        """The canonical 32-byte public key. Public material only."""

        return self._public_key_bytes

    def __eq__(self, other: object) -> bool:
        if type(other) is not TrustedEvidenceVerificationKey:
            return NotImplemented
        return self._public_key_bytes == other._public_key_bytes

    def __hash__(self) -> int:
        return hash((TrustedEvidenceVerificationKey, self._public_key_bytes))

    def __repr__(self) -> str:
        return f"TrustedEvidenceVerificationKey({self._public_key_bytes.hex()})"

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Return ``True`` iff the maintained backend accepts the signature.

        Every invalid or malformed input yields ``False`` rather than raising,
        so a caller has one fail-closed boolean to branch on. Malleability, the
        ``S >= L`` bound, non-canonical ``R`` encodings and low-order ``R`` are
        all the backend's responsibility — this package no longer implements
        the signature equation and therefore cannot get it subtly wrong.
        """

        if type(message) is not bytes:
            return False
        if type(signature) is not bytes or len(signature) != ED25519_SIGNATURE_SIZE:
            return False
        try:
            self._backend_public_key.verify(signature, message)
        except _InvalidSignature:
            return False
        except Exception:
            return False
        return True
