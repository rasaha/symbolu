"""Password hashing using Argon2id (DEC-011).

Wrapped behind a small interface so the identity store can later be swapped for a
managed identity provider without touching callers.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id is the default type for PasswordHasher.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed stored hash etc. Treat as non-match; never raise to caller.
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
