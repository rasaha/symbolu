"""Deterministic, domain-separated SHA-256 fingerprinting.

Every product fingerprint is content-derived and stable across processes:

* domain separation prevents a fingerprint computed for one record type from
  ever colliding with an equal payload of another type;
* payloads are canonicalized (sorted keys, compact separators) so key/order
  variation cannot change the digest;
* there are **no** hidden time reads, no randomness, and no mutable global
  state — the same inputs always yield the same digest (deterministic replay).

This mirrors the repository-standard "domain-separated SHA-256" convention used
by the neutral contracts and providers.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

#: Product-wide namespace prefix. Combined with a per-record domain label so
#: no two record families share a preimage space.
_NAMESPACE = "ugence.code_governance"


def canonicalize(payload: Any) -> str:
    """Return a stable canonical JSON string for ``payload``.

    Mappings are serialized with sorted keys; tuples/lists preserve order (the
    caller decides whether order is significant). Non-JSON scalars (datetimes,
    enums) fall back to ``str`` deterministically.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def domain_hash(domain: str, payload: Any) -> str:
    """Compute a domain-separated SHA-256 hex digest over ``payload``.

    ``domain`` is a stable, versioned label (e.g. ``"governed_change_identity.v1"``).
    The digest changes if and only if the domain or the canonical payload changes.
    """
    preimage = f"{_NAMESPACE}:{domain}\n{canonicalize(payload)}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def content_digest(payload: Mapping[str, Any]) -> str:
    """Content digest for a normalized evidence payload (content-addressing)."""
    return domain_hash("content.v1", payload)


__all__ = ["canonicalize", "domain_hash", "content_digest"]
