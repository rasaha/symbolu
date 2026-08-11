"""Deterministic canonical serialization + content digests for the canonical
capacity-intelligence layer.

This module is a **local, stdlib-only** re-implementation of the repository's canonical
serialization conventions (sorted keys, NFC strings, RFC3339-UTC timestamps, `sha256:`
prefixed hex digests). It is deliberately NOT imported from the Risk Authority or any
other package: the Cloud Scaling Controller is a numpy-only advisory leaf and must not
gain a reverse dependency on an authority/orchestration package merely to reuse a
convenience type. The rules here mirror those conventions so a future, separately
governed integration package can reference the resulting digest as a stable, opaque
content identity.

Digest semantics (documented once, referenced by every artifact that carries a digest):

* **Algorithm / encoding.** SHA-256 over the canonical byte stream, rendered as
  lowercase hex with a ``sha256:`` prefix (:data:`DIGEST_PREFIX`).
* **Domain separation.** The preimage is
  ``"<namespace>\\x1f<domain>\\x1f<schema_version>\\x1f<canonical_json>"`` so a digest
  computed for one artifact kind can never collide with another.
* **Key ordering.** Object keys are sorted lexicographically (by NFC-normalized key).
* **Number representation.** ``int``/``bool`` are emitted natively (``bool`` handled
  *before* ``int``). ``float`` uses Python's round-trippable ``repr`` via ``json``;
  ``-0.0`` is normalized to ``0.0``; ``NaN``/``±inf`` are **rejected** (fail closed).
* **Strings.** Unicode NFC-normalized.
* **Timestamps.** ``datetime`` → RFC3339 UTC ``Z`` with microseconds; naive datetimes
  are treated as UTC.
* **Enums.** Serialized by ``.value``.
* **Null / optional.** ``None`` is preserved as ``null`` (never silently dropped), so a
  present-but-null field is distinguishable from an absent one at the digest layer.
* **Collections.** ``list``/``tuple`` preserve order; ``set``/``frozenset`` are sorted.

This canonicalizer is *float-tolerant* (metrics are floats) and therefore intentionally
differs from a strict integer-minor-units canonicalizer. The digest it produces is an
evidence **identity**, not a signature, authorization, or risk verdict.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from typing import Any

NAMESPACE = "ugence_cloud_scaling_controller"
DIGEST_PREFIX = "sha256:"

# Unit separator (0x1f) used to build unambiguous, domain-separated digest preimages.
_SEP = "\x1f"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized deterministically (fail closed)."""


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _rfc3339(value: datetime) -> str:
    """Render a datetime as RFC3339 UTC with microseconds (naive treated as UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def to_canonical_obj(value: Any) -> Any:
    """Recursively convert ``value`` into a JSON-safe, canonically-ordered structure.

    Fails closed on non-finite floats and unsupported types.
    """
    if value is None:
        return None
    # bool BEFORE int (bool is a subclass of int).
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalizationError(f"non-finite float is not canonicalizable: {value!r}")
        # Normalize negative zero so +0.0 and -0.0 digest identically.
        return 0.0 if value == 0.0 else value
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, Enum):
        return to_canonical_obj(value.value)
    if isinstance(value, datetime):
        return _rfc3339(value)
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalizationError(
                    f"map keys must be strings for canonical form, got {type(k).__name__}"
                )
            out[_nfc(k)] = to_canonical_obj(v)
        # Sort by NFC-normalized key for stable ordering.
        return {k: out[k] for k in sorted(out)}
    if isinstance(value, (list, tuple)):
        return [to_canonical_obj(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(to_canonical_obj(v) for v in value)
    raise CanonicalizationError(f"unsupported type for canonicalization: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return a compact, deterministic JSON string for ``value``."""
    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    """UTF-8 encoding of :func:`canonical_json` — the digest input."""
    return canonical_json(value).encode("utf-8")


def content_digest(domain: str, schema_version: str, value: Any) -> str:
    """Compute a domain-separated ``sha256:``-prefixed content digest.

    ``domain`` names the artifact kind (e.g. ``"capacity_state"``); ``schema_version``
    binds the digest to the schema so a version bump changes identity. The digest is a
    content identity only — not a signature, authorization, or risk verdict.
    """
    preimage = _SEP.join((NAMESPACE, domain, schema_version, canonical_json(value)))
    return DIGEST_PREFIX + hashlib.sha256(preimage.encode("utf-8")).hexdigest()


__all__ = [
    "NAMESPACE",
    "DIGEST_PREFIX",
    "CanonicalizationError",
    "to_canonical_obj",
    "canonical_json",
    "canonical_bytes",
    "content_digest",
]
