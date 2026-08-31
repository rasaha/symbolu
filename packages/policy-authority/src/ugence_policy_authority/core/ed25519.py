"""Ed25519 (RFC 8032) reference implementation — stdlib only.

This follows the repository's already-established convention for an authority
leaf that signs: ``risk_authority/crypto/signing.py`` ships the same pure-Python
RFC 8032 reference implementation so the package stays a stdlib-only leaf whose
conformance suite runs in an isolated ``--no-index`` install. This module
reproduces that convention rather than importing ``risk_authority``, which
would create a reverse dependency on another authority's internals (ADR §21).

This is a **standard algorithm implemented to its RFC**, not bespoke
cryptography, and not a hash or an HMAC dressed up as a signature.

Security note — as in the existing convention, this is a correct but
unoptimised reference implementation intended for deterministic tests and
reference deployments. A production deployment must verify with a vetted
library and hold authority signing keys in an HSM / managed KMS. The public
shapes (:class:`SigningKey` / :class:`VerifyKey`) are deliberately narrow so
they can be swapped for such a backend without touching any caller — the
authority itself only ever talks to the
:class:`~ugence_policy_authority.signing.PolicySigner` /
:class:`~ugence_policy_authority.signing.PolicySignatureVerifier`
protocols.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

__all__ = [
    "SIGNATURE_ALG",
    "SEED_SIZE",
    "PUBLIC_KEY_SIZE",
    "SIGNATURE_SIZE",
    "SigningKey",
    "VerifyKey",
    "BadSignatureError",
]

SIGNATURE_ALG = "ed25519"
SEED_SIZE = 32
PUBLIC_KEY_SIZE = 32
SIGNATURE_SIZE = 64

# ---------------------------------------------------------------------------
# RFC 8032 field / curve arithmetic (edwards25519)
# ---------------------------------------------------------------------------
_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    """The inverse of ``x`` modulo ``_Q``, by extended Euclid rather than by Fermat.

    ``pow(x, _Q - 2, _Q)`` is RFC 8032's own spelling and is correct, but it is a
    255-bit modular exponentiation, and the affine addition law below calls this twice
    for every point addition. It dominated every suite that signs: profiling the Cloud
    Scaling guard sweeps found ``builtins.pow`` was ~93% of a mutant's entire runtime,
    204,341 calls behind 102,169 point additions, and the two slowest sweeps in CI spent
    838 of their 885 runner-minutes here.

    ``pow(x, -1, _Q)`` computes the same value by extended Euclid in C — eight times
    faster on this modulus, measured, and identical on every invertible input.

    The ``try`` is load-bearing, not defensive styling. Fermat's form silently returns 0
    for a non-invertible base; the Euclid form raises ``ValueError``. That difference is
    not academic here: ``_xrecover`` calls this on an attacker-influenced field element,
    and a guard sweep neutralises refusals to see which gate decided, so an input that
    reaches this with ``x % _Q == 0`` must keep answering 0. Mapping the exception back
    makes the two forms equal on *every* integer, which is what the pinning test asserts.
    """

    try:
        return pow(x, -1, _Q)
    except ValueError:  # x is congruent to 0 mod _Q; Fermat's form yields 0 here
        return 0


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
_B = (_BX % _Q, _BY % _Q)


def _edwards_add(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    denom = _D * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + denom) % _Q
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - denom) % _Q
    return (x3 % _Q, y3 % _Q)


def _scalarmult(p: tuple[int, int], e: int) -> tuple[int, int]:
    # Iterative double-and-add (avoids deep recursion on the ~253-bit scalar).
    result = (0, 1)
    addend = p
    while e > 0:
        if e & 1:
            result = _edwards_add(result, addend)
        addend = _edwards_add(addend, addend)
        e >>= 1
    return result


def _encode_int(y: int) -> bytes:
    return y.to_bytes(32, "little")


def _encode_point(p: tuple[int, int]) -> bytes:
    x, y = p
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _clamp_scalar(h: bytes) -> int:
    return 2 ** 254 + sum(2 ** i * _bit(h, i) for i in range(3, 254))


def _is_on_curve(p: tuple[int, int]) -> bool:
    x, y = p
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


def _decode_point(s: bytes) -> tuple[int, int]:
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != _bit(s, 255):
        x = _Q - x
    point = (x, y)
    if not _is_on_curve(point):
        raise BadSignatureError("point is not on the edwards25519 curve")
    return point


class BadSignatureError(Exception):
    """Raised internally when signature material is malformed."""


def _public_from_seed(seed: bytes) -> bytes:
    h = _sha512(seed)
    a = _clamp_scalar(h)
    return _encode_point(_scalarmult(_B, a))


@dataclass(frozen=True)
class SigningKey:
    """An Ed25519 private key (32-byte seed).

    Held only by a signer implementation. It is never a field of any authority
    record, so private key material cannot leak into a stored, serialized, or
    returned contract object.
    """

    seed: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.seed, (bytes, bytearray)):
            raise ValueError("seed must be bytes")
        if len(self.seed) != SEED_SIZE:
            raise ValueError(f"seed must be {SEED_SIZE} bytes, got {len(self.seed)}")
        object.__setattr__(self, "seed", bytes(self.seed))

    @classmethod
    def generate(cls) -> "SigningKey":
        return cls(os.urandom(SEED_SIZE))

    @classmethod
    def from_seed(cls, seed: bytes) -> "SigningKey":
        return cls(bytes(seed))

    @property
    def verify_key(self) -> "VerifyKey":
        return VerifyKey(_public_from_seed(self.seed))

    def sign(self, message: bytes) -> bytes:
        seed = self.seed
        h = _sha512(seed)
        a = _clamp_scalar(h)
        pk = _encode_point(_scalarmult(_B, a))
        r = int.from_bytes(_sha512(h[32:64] + message), "little")
        big_r = _scalarmult(_B, r)
        r_enc = _encode_point(big_r)
        k = int.from_bytes(_sha512(r_enc + pk + message), "little")
        s = (r + k * a) % _L
        return r_enc + _encode_int(s)

    def __repr__(self) -> str:  # pragma: no cover - defensive, never asserted on
        return "SigningKey(<redacted>)"


@dataclass(frozen=True)
class VerifyKey:
    """An Ed25519 public key (32 bytes)."""

    public_bytes: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.public_bytes, (bytes, bytearray)):
            raise ValueError("public key must be bytes")
        if len(self.public_bytes) != PUBLIC_KEY_SIZE:
            raise ValueError(
                f"public key must be {PUBLIC_KEY_SIZE} bytes, got {len(self.public_bytes)}"
            )
        object.__setattr__(self, "public_bytes", bytes(self.public_bytes))

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Return ``True`` iff ``signature`` is a valid Ed25519 signature.

        Every invalid or malformed input yields ``False`` rather than raising,
        so a caller has a single fail-closed boolean to branch on. Verification
        is an algebraic curve-equation check whose work does not vary with how
        *close* a forged signature is to a valid one, and the final comparison
        is between decoded curve points, not a byte-wise scan of secret
        material.
        """

        if not isinstance(signature, (bytes, bytearray)) or len(signature) != SIGNATURE_SIZE:
            return False
        try:
            big_r = _decode_point(bytes(signature[:32]))
            big_a = _decode_point(self.public_bytes)
            s = int.from_bytes(signature[32:64], "little")
            if s >= _L:
                return False
            k = int.from_bytes(
                _sha512(bytes(signature[:32]) + self.public_bytes + message), "little"
            )
            left = _scalarmult(_B, s)
            right = _edwards_add(big_r, _scalarmult(big_a, k))
            return left == right
        except BadSignatureError:
            return False
