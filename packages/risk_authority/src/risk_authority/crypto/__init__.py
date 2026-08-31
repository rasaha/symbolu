"""Cryptographic foundation: canonicalization, hashing, signing, keys."""

from __future__ import annotations

from .canonical import canonical_bytes, canonical_dumps, to_canonical_obj
from .hashing import DIGEST_PREFIX, digest, sha256_hex
from .keys import KeyRing, SigningKeyRecord
from .signing import (
    SIGNATURE_ALG,
    BadSignatureError,
    SigningKey,
    VerifyKey,
)

__all__ = [
    "to_canonical_obj",
    "canonical_dumps",
    "canonical_bytes",
    "digest",
    "sha256_hex",
    "DIGEST_PREFIX",
    "SigningKey",
    "VerifyKey",
    "SIGNATURE_ALG",
    "BadSignatureError",
    "SigningKeyRecord",
    "KeyRing",
]
