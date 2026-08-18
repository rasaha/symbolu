"""Ed25519 (RFC 8032) reference implementation — stdlib only.

This reproduces the repository's **already-established convention** for an
authority leaf that signs. Two merged authorities ship exactly this module:

* ``risk_authority/crypto/signing.py`` — the first to establish it;
* ``ugence_policy_authority/core/ed25519.py`` — which adopted it verbatim in
  posture, recording that it "reproduces this convention rather than importing
  ``risk_authority``, which would create a reverse dependency on another
  authority's internals".

TEV-2 is in the same position and takes the same route, for the same reasons
plus two of its own.

Why not the ``cryptography`` distribution
-----------------------------------------
The instruction for this milestone was to prefer Ed25519 **through the
maintained cryptography library** *unless the ADR or repository constraints
require otherwise*. Three repository constraints require otherwise, and the
**algorithm profile is unchanged either way — this is Ed25519**:

1. **ADR §23 fixes the dependency matrix.** TAP "may consume
   ``governance-contracts`` only". A third-party runtime dependency is not an
   arrow the ratified matrix draws, and TEV-1 shipped narrower still — zero
   runtime dependencies — with ``tests/packaging/test_dependency_boundary.py``
   asserting that the distribution declares none and that no module imports
   anything but the standard library. Adding ``cryptography`` would break a
   merged, ratified test, which is a contract change TEV-2 is not authorized to
   make.
2. **The isolated ``--no-index`` install proof depends on it.** The distribution
   verifier builds a wheel and installs it into a clean virtual environment with
   ``--no-index``, then runs the adversarial probes *inside* that environment. A
   compiled third-party dependency cannot resolve under ``--no-index``, so the
   strongest packaging proof this package has would have to be weakened to
   accommodate the library.
3. **DD-10 keeps production key custody deferred.** "Production persistence,
   distributed concurrency, and HSM/KMS posture for both capabilities … mirrors
   Policy Authority §15.7; **reference-grade first**." A reference-grade signer
   is precisely what the ADR asks TEV-2 for.

This is a **standard algorithm implemented to its RFC**, not bespoke
cryptography, not a hash or an HMAC dressed up as a signature, and not a
caller-selectable algorithm menu. ``tests/authority/test_ed25519_rfc8032.py``
pins the official RFC 8032 §7.1 test vectors and reproduces every one of them,
so conformance is demonstrated against the standard rather than asserted.

Security posture — stated plainly
---------------------------------
This is a **reference** implementation intended for deterministic tests and
reference deployments, not a hardened production cryptographic library. Two
things follow, and both are stated rather than glossed:

* **It is not constant-time.** Python's arbitrary-precision integers do not
  offer constant-time arithmetic at all, so this module cannot claim resistance
  to timing or other side-channel analysis, and does not. Signing is the
  operation that touches secret material; a deployment whose threat model
  includes local side channels must not sign with this module.
* **A production deployment must verify with a vetted library and hold
  authority signing keys in an HSM or managed KMS** (DD-10).

It does use the RFC's own extended-coordinate group law (§5.1.4) rather than
the naive affine form, which removes a 255-bit modular exponentiation from every
point addition. That is an algebraic reorganisation specified by the RFC itself,
not a deviation from it: the published §7.1 vectors reproduce byte-for-byte
either way, and ``tests/authority/test_ed25519_rfc8032.py`` proves it against
all five of them.

The public shapes
(:class:`TrustedEvidenceSigningKey` / :class:`TrustedEvidenceVerificationKey`)
are deliberately narrow so they can be swapped for such a backend without
touching any caller: the authority itself only ever talks to the
:class:`~.signing.ReceiptSignerPort` protocol, and a receipt signer receives a
package-constructed :class:`~.signing.ReceiptSigningInput`, never free bytes.

No key generation here
----------------------
There is no ``generate()``. Key generation needs an entropy source, and
``os``/``secrets``/``random`` are banned package-wide by
``tests/packaging/test_no_clock_or_environment.py`` — every output of this
package must be a pure function of its inputs. Credential issuance is also
explicitly outside the TEV-2 boundary. A seed enters through the narrow
:class:`TrustedEvidenceSigningKey` boundary from the composition root, or from a
clearly-labelled non-production test vector, and nowhere else.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

__all__ = [
    "ED25519_SEED_SIZE",
    "ED25519_PUBLIC_KEY_SIZE",
    "ED25519_SIGNATURE_SIZE",
    "TrustedEvidenceSigningKey",
    "TrustedEvidenceVerificationKey",
]

#: Byte length of an Ed25519 private seed (RFC 8032 §5.1.5).
ED25519_SEED_SIZE = 32
#: Byte length of an Ed25519 public key (RFC 8032 §5.1.5).
ED25519_PUBLIC_KEY_SIZE = 32
#: Byte length of an Ed25519 signature (RFC 8032 §5.1.6).
ED25519_SIGNATURE_SIZE = 64


# --------------------------------------------------------------------------- #
# RFC 8032 field / curve arithmetic (edwards25519)
# --------------------------------------------------------------------------- #

_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


_D = (-121665 * _inv(121666)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = (4 * _inv(5)) % _Q
_BX = _xrecover(_BY)

# --------------------------------------------------------------------------- #
# Extended homogeneous coordinates, exactly as RFC 8032 §5.1.4 specifies
#
# A point is ``(X, Y, Z, T)`` with ``x = X/Z``, ``y = Y/Z`` and ``x*y = T/Z``.
# The RFC gives these formulas precisely so that group operations need **no**
# modular inversion: in affine coordinates every addition costs one 255-bit
# modular exponentiation, which made the naive form roughly two orders of
# magnitude slower than it needs to be. Exactly one inversion remains, at the
# single point where a result is converted back to affine for encoding.
#
# The addition formula is *complete* on edwards25519 — it is correct for every
# pair of points including doubling and the identity — so there is no special
# case to get wrong and no branch that depends on secret data.
# --------------------------------------------------------------------------- #

_IDENTITY = (0, 1, 1, 0)
_B = (_BX % _Q, _BY % _Q, 1, (_BX * _BY) % _Q)


def _point_add(p: tuple, q: tuple) -> tuple:
    """RFC 8032 §5.1.4 — add two extended points. Complete; no special cases."""

    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _Q
    b = (y1 + x1) * (y2 + x2) % _Q
    c = 2 * t1 * t2 * _D % _Q
    d = 2 * z1 * z2 % _Q
    e = b - a
    f = d - c
    g = d + c
    h = b + a
    return (e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q)


def _scalarmult(p: tuple, e: int) -> tuple:
    """Iterative double-and-add over extended coordinates."""

    result = _IDENTITY
    addend = p
    while e > 0:
        if e & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        e >>= 1
    return result


def _to_affine(p: tuple) -> tuple:
    """The one modular inversion in the whole module."""

    x, y, z, _t = p
    inverse = _inv(z)
    return (x * inverse % _Q, y * inverse % _Q)


def _points_equal(p: tuple, q: tuple) -> bool:
    """Compare in projective form: ``X1*Z2 == X2*Z1`` and likewise for ``Y``."""

    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % _Q == 0 and (y1 * z2 - y2 * z1) % _Q == 0


def _encode_int(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _encode_point(p: tuple) -> bytes:
    x, y = _to_affine(p)
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _clamp_scalar(h: bytes) -> int:
    return 2 ** 254 + sum(2 ** i * _bit(h, i) for i in range(3, 254))


def _is_on_curve(x: int, y: int) -> bool:
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


class _MalformedPoint(Exception):
    """Raised internally when signature or key material is not a curve point."""


def _decode_point(s: bytes) -> tuple:
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    if y >= _Q:
        raise _MalformedPoint("y coordinate is not a canonical field element")
    x = _xrecover(y)
    if (x & 1) != _bit(s, 255):
        x = _Q - x
    if not _is_on_curve(x, y):
        raise _MalformedPoint("point is not on the edwards25519 curve")
    return (x, y, 1, x * y % _Q)


def _public_from_seed(seed: bytes) -> bytes:
    h = _sha512(seed)
    a = _clamp_scalar(h)
    return _encode_point(_scalarmult(_B, a))


# --------------------------------------------------------------------------- #
# The two narrow key shapes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TrustedEvidenceSigningKey:
    """An Ed25519 private key (32-byte seed) — the only private material here.

    Held **only** by a signer implementation at the composition root. It is
    never a field of any trust anchor, envelope, determination, receipt, audit
    record or verification result; the canonical encoder rejects ``bytes``
    outright, so no path exists by which a seed could reach canonical JSON or a
    digest. Its ``__repr__`` is redacted, so it cannot leak through a traceback,
    a log line, or a debugger frame dump.

    There is no accessor that returns the seed and no ``generate()``: seeds
    enter here and go no further.
    """

    seed: bytes

    def __post_init__(self) -> None:
        if type(self.seed) is not bytes:
            raise ValueError(
                "TrustedEvidenceSigningKey.seed must be exactly bytes "
                f"(got {type(self.seed).__name__})"
            )
        if len(self.seed) != ED25519_SEED_SIZE:
            raise ValueError(
                f"TrustedEvidenceSigningKey.seed must be {ED25519_SEED_SIZE} bytes, "
                f"got {len(self.seed)}"
            )

    @property
    def verification_key(self) -> "TrustedEvidenceVerificationKey":
        """Publish the public half. The seed is not derivable from the result."""

        return TrustedEvidenceVerificationKey(_public_from_seed(self.seed))

    def sign(self, message: bytes) -> bytes:
        """Return the RFC 8032 Ed25519 signature over ``message``.

        Deliberately **not** a public API surface of the package: reaching this
        method requires already holding the private key, which only a signer at
        the composition root does. The package exposes no route by which a
        caller can hand arbitrary bytes to a configured signer — see
        :class:`~.signing.ReceiptSigningInput`.
        """

        if type(message) is not bytes:
            raise ValueError("message to sign must be exactly bytes")
        seed = self.seed
        h = _sha512(seed)
        a = _clamp_scalar(h)
        pk = _encode_point(_scalarmult(_B, a))
        r = int.from_bytes(_sha512(h[32:64] + message), "little")
        r_enc = _encode_point(_scalarmult(_B, r))
        k = int.from_bytes(_sha512(r_enc + pk + message), "little")
        s = (r + k * a) % _L
        return r_enc + _encode_int(s)

    def __repr__(self) -> str:
        """Redacted. Private key material never renders."""

        return "TrustedEvidenceSigningKey(<redacted>)"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class TrustedEvidenceVerificationKey:
    """An Ed25519 public key (32 bytes). Public material only."""

    public_key_bytes: bytes

    def __post_init__(self) -> None:
        if type(self.public_key_bytes) is not bytes:
            raise ValueError(
                "TrustedEvidenceVerificationKey.public_key_bytes must be exactly "
                f"bytes (got {type(self.public_key_bytes).__name__})"
            )
        if len(self.public_key_bytes) != ED25519_PUBLIC_KEY_SIZE:
            raise ValueError(
                "TrustedEvidenceVerificationKey.public_key_bytes must be "
                f"{ED25519_PUBLIC_KEY_SIZE} bytes, got {len(self.public_key_bytes)}"
            )

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Return ``True`` iff ``signature`` is a valid Ed25519 signature.

        Every invalid or malformed input yields ``False`` rather than raising,
        so a caller has a single fail-closed boolean to branch on. A truncated,
        extended, non-canonical or off-curve signature is ``False``, and an
        ``s`` scalar at or above the group order ``L`` is ``False`` — which is
        the malleability check RFC 8032 §5.1.7 requires and which a naive
        implementation omits.
        """

        if type(message) is not bytes:
            return False
        if type(signature) is not bytes or len(signature) != ED25519_SIGNATURE_SIZE:
            return False
        try:
            big_r = _decode_point(signature[:32])
            big_a = _decode_point(self.public_key_bytes)
            s = int.from_bytes(signature[32:64], "little")
            if s >= _L:
                return False
            k = int.from_bytes(
                _sha512(signature[:32] + self.public_key_bytes + message), "little"
            )
            left = _scalarmult(_B, s)
            right = _point_add(big_r, _scalarmult(big_a, k))
            return _points_equal(left, right)
        except _MalformedPoint:
            return False
