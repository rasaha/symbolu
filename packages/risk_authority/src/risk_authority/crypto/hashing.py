"""Content digests over the canonical serialization.

Every WorkflowIR digest, evidence-snapshot digest, model digest, action digest
and reconciliation payload digest in the package flows through here so the
digest of an object depends only on its canonical meaning, never on its
transport encoding (spec §14, §27).
"""

from __future__ import annotations

import hashlib
from typing import Any

from .canonical import canonical_bytes

__all__ = ["sha256_hex", "digest", "DIGEST_PREFIX"]

DIGEST_PREFIX = "sha256:"


def sha256_hex(data: bytes) -> str:
    """Return the ``sha256:<hex>`` digest of raw bytes."""

    return DIGEST_PREFIX + hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    """Return the ``sha256:<hex>`` digest of ``value``'s canonical form."""

    return sha256_hex(canonical_bytes(value))
