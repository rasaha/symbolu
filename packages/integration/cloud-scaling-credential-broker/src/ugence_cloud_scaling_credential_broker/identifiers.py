"""Ratified identifiers and limits for Phase 5X (ADR 5X, D-1, D-4, D-5)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

__all__ = [
    "CREDENTIAL_PROFILE",
    "GRANT_ID_PREFIX",
    "REQUEST_DIGEST_PREFIX",
    "MAX_TTL_CAP",
    "DEFAULT_TTL_CAP",
    "FORBIDDEN_FIELD_NAMES",
    "HANDLE_REF_PATTERN",
]

#: The one credential profile this release speaks. A broker must advertise exactly it.
CREDENTIAL_PROFILE: Final[str] = "ugence.cloud-scaling.credential/v1"
#: Grant ids are derived from the request digest, never allocated (D-4).
GRANT_ID_PREFIX: Final[str] = "cred.v1:"
REQUEST_DIGEST_PREFIX: Final[str] = "credreq.v1:"
#: The hard ceiling on any composition root's ttl cap (D-4). Enforced at construction.
MAX_TTL_CAP: Final[timedelta] = timedelta(minutes=15)
DEFAULT_TTL_CAP: Final[timedelta] = timedelta(minutes=10)
#: Names no dataclass in this package may carry (D-5): the secret never has a slot.
FORBIDDEN_FIELD_NAMES: Final[frozenset] = frozenset({
    "secret", "secrets", "token", "access_token", "refresh_token", "password", "passphrase",
    "key_material", "private_key", "secret_key", "access_key", "session_token", "kubeconfig",
    "bearer", "credential", "credentials", "client_secret",
})
#: An opaque handle *reference*: short, printable, no whitespace, no encoding of material.
HANDLE_REF_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
