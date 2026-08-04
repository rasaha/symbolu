"""Deployment credential hashing (P3E §9).

Argon2id is preferred, but this offline build environment ships no argon2/passlib
wheel, so we use the Python standard library's ``hashlib.scrypt`` — a memory-hard
password KDF — with a constant-time verifier (``hmac.compare_digest``). The hash
format is self-describing so a future Argon2id migration is additive:

    scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>

No plaintext password is ever stored, logged, or printed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

# scrypt cost parameters (RFC 7914). n must be a power of two.
_N = 2 ** 15
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16
_MAXMEM = 128 * _R * _N * 2  # headroom over scrypt's 128*r*n requirement


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a self-describing scrypt hash string for ``password``."""
    if not password:
        raise ValueError("password must not be empty")
    salt = salt if salt is not None else os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(dk)}"


def is_valid_hash_format(encoded: str) -> bool:
    try:
        parse_hash(encoded)
        return True
    except (ValueError, Exception):  # noqa: BLE001 - any malformed input is invalid
        return False


def parse_hash(encoded: str) -> tuple[int, int, int, bytes, bytes]:
    parts = encoded.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        raise ValueError("unsupported password hash format")
    n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
    if n <= 1 or (n & (n - 1)) != 0:
        raise ValueError("scrypt n must be a power of two > 1")
    salt, dk = _unb64(parts[4]), _unb64(parts[5])
    if not salt or not dk:
        raise ValueError("empty salt or digest")
    return n, r, p, salt, dk


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of ``password`` against a stored hash."""
    try:
        n, r, p, salt, expected = parse_hash(encoded)
    except (ValueError, Exception):  # noqa: BLE001
        return False
    candidate = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected), maxmem=128 * r * n * 2
    )
    return hmac.compare_digest(candidate, expected)
