"""Content-addressing helpers.

A single hashing primitive over canonical JSON, plus a digest-chain builder used
by the audit schema and release manifest. Digests are deterministic functions of
logical content only — no timestamps, no filesystem metadata.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, List

from . import canonical_json

#: Prefix marking a logical (timestamp-free) digest.
DIGEST_PREFIX = "sha256:"


def digest(value: Any) -> str:
    """Return ``sha256:<hex>`` over the canonical JSON encoding of ``value``."""
    encoded = canonical_json.dumps(value).encode("utf-8")
    return DIGEST_PREFIX + hashlib.sha256(encoded).hexdigest()


def digest_bytes(data: bytes) -> str:
    """Return ``sha256:<hex>`` over raw bytes."""
    return DIGEST_PREFIX + hashlib.sha256(data).hexdigest()


def chain(events: Iterable[Any]) -> List[str]:
    """Build a deterministic digest chain over ``events``.

    Each element's digest folds in the previous element's digest, so the final
    entry commits to the whole ordered sequence. This is a canonical,
    reproducible chain — **not** a cryptographic-immutability guarantee.
    """
    out: List[str] = []
    previous = DIGEST_PREFIX + "0" * 64
    for event in events:
        out.append(digest({"previous_event_digest": previous, "event": event}))
        previous = out[-1]
    return out
