"""Deployment credential hashing (P3E §9, completion §5).

**Argon2id** is the password KDF (via the pinned `argon2-cffi`), using the standard
encoded hash format `$argon2id$v=19$m=...,t=...,p=...$salt$hash` with a library-managed
salt and constant-time verification. Cost parameters are bounded, and an operator-
supplied stored hash whose parameters exceed the approved maxima is rejected **before**
the KDF runs (so a maliciously large `m`/`t`/`p` cannot be used for a memory/CPU DoS).

Legacy `scrypt$v=1$...` hashes are still *verified* (constant-time) for migration, but
new hashes are always Argon2id. No plaintext password is ever stored, logged, or printed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError

# Argon2id cost bounds (approved envelope). memory in KiB.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 64 * 1024  # 64 MiB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16

# Maximum parameters we will accept in a *stored* hash before invoking the verifier.
MAX_ARGON2_MEMORY_COST = 256 * 1024  # 256 MiB
MAX_ARGON2_TIME_COST = 10
MAX_ARGON2_PARALLELISM = 8

_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
    type=Type.ID,
)

_ARGON2_PARAMS_RE = re.compile(r"^\$argon2id\$v=\d+\$m=(\d+),t=(\d+),p=(\d+)\$")


# -- Argon2id (primary) ----------------------------------------------------
def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    return _hasher.hash(password)


def _argon2_params_within_bounds(encoded: str) -> bool:
    m = _ARGON2_PARAMS_RE.match(encoded)
    if not m:
        return False
    memory, time_cost, parallelism = (int(x) for x in m.groups())
    return (
        0 < memory <= MAX_ARGON2_MEMORY_COST
        and 0 < time_cost <= MAX_ARGON2_TIME_COST
        and 0 < parallelism <= MAX_ARGON2_PARALLELISM
    )


# -- legacy scrypt (verify only, for migration) ----------------------------
_SCRYPT_MAX_N = 2 ** 20


def _verify_scrypt(password: str, encoded: str) -> bool:
    # accepts both "scrypt$n$r$p$salt$hash" and "scrypt$v=1$n=..$r=..$p=..$salt=..$digest=.."
    try:
        if encoded.startswith("scrypt$v="):
            fields = dict(part.split("=", 1) for part in encoded.split("$")[2:] if "=" in part)
            n, r, p = int(fields["n"]), int(fields["r"]), int(fields["p"])
            salt = base64.b64decode(fields["salt"]); expected = base64.b64decode(fields["digest"])
        else:
            _, n_s, r_s, p_s, salt_b, hash_b = encoded.split("$")
            n, r, p = int(n_s), int(r_s), int(p_s)
            salt = base64.b64decode(salt_b); expected = base64.b64decode(hash_b)
    except (ValueError, KeyError, Exception):  # noqa: BLE001
        return False
    if n <= 1 or (n & (n - 1)) != 0 or n > _SCRYPT_MAX_N:  # reject excessive/invalid cost before KDF
        return False
    if not salt or not expected:
        return False
    candidate = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected), maxmem=128 * r * n * 2)
    return hmac.compare_digest(candidate, expected)


# -- public API ------------------------------------------------------------
def is_valid_hash_format(encoded: str) -> bool:
    if not encoded:
        return False
    if encoded.startswith("$argon2id$"):
        return _argon2_params_within_bounds(encoded)
    if encoded.startswith("scrypt$"):
        # structurally parseable legacy record with parameters within bounds
        try:
            if encoded.startswith("scrypt$v="):
                fields = dict(part.split("=", 1) for part in encoded.split("$")[2:] if "=" in part)
                n, r, p = int(fields["n"]), int(fields["r"]), int(fields["p"])
                base64.b64decode(fields["salt"]); base64.b64decode(fields["digest"])
            else:
                _, n_s, r_s, p_s, salt_b, hash_b = encoded.split("$")
                n, r, p = int(n_s), int(r_s), int(p_s)
                base64.b64decode(salt_b); base64.b64decode(hash_b)
            return n > 1 and (n & (n - 1)) == 0 and n <= _SCRYPT_MAX_N and r > 0 and p > 0
        except (ValueError, KeyError):
            return False
    return False


def verify_password(password: str, encoded: str) -> bool:
    if not encoded:
        return False
    if encoded.startswith("$argon2id$"):
        if not _argon2_params_within_bounds(encoded):  # cap cost BEFORE invoking the KDF
            return False
        try:
            return _hasher.verify(encoded, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        except Exception:  # noqa: BLE001 - any malformed record fails closed
            return False
    if encoded.startswith("scrypt$"):
        return _verify_scrypt(password, encoded)
    return False
