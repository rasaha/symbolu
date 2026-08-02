"""Domain-separated SHA-256 fingerprinting (design §11, §16).

Preimage format (frozen), mirroring the merged design:

    action_clearance \x1f <domain> \x1f v1 \x1f <canonical_json>

``\x1f`` is the ASCII unit separator (0x1F). Fingerprints are content-derived and
exclude random ids, storage/wall-clock timestamps, database metadata, memory
addresses, unordered maps, and mutable lifecycle state.
"""
from __future__ import annotations

import hashlib
from typing import Any

from ..normalization import canonical_json

_NAMESPACE = "action_clearance"
_US = "\x1f"

# Canonical single-token domains (merged schema x-fingerprint domains).
DOMAIN_SIGNAL_CONTENT = "signal_content"
DOMAIN_SIGNAL_PROVENANCE = "signal_provenance"
DOMAIN_SIGNAL_BUNDLE = "signal_bundle"
DOMAIN_ACTION = "action"
DOMAIN_REQUEST = "request"
DOMAIN_RESULT = "result"


def domain_fingerprint(domain: str, payload: Any) -> str:
    """Compute the domain-separated SHA-256 hex digest over ``payload``."""
    preimage = f"{_NAMESPACE}{_US}{domain}{_US}v1{_US}{canonical_json(payload)}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def signal_content_fingerprint(payload: Any) -> str:
    return domain_fingerprint(DOMAIN_SIGNAL_CONTENT, payload)


def signal_provenance_fingerprint(payload: Any) -> str:
    return domain_fingerprint(DOMAIN_SIGNAL_PROVENANCE, payload)


def signal_bundle_fingerprint(payload: Any) -> str:
    return domain_fingerprint(DOMAIN_SIGNAL_BUNDLE, payload)


def authorized_action_fingerprint(payload: Any) -> str:
    return domain_fingerprint(DOMAIN_ACTION, payload)


def clearance_request_fingerprint(payload: Any) -> str:
    return domain_fingerprint(DOMAIN_REQUEST, payload)


def clearance_result_fingerprint(payload: Any) -> str:
    return domain_fingerprint(DOMAIN_RESULT, payload)


__all__ = [
    "domain_fingerprint",
    "signal_content_fingerprint",
    "signal_provenance_fingerprint",
    "signal_bundle_fingerprint",
    "authorized_action_fingerprint",
    "clearance_request_fingerprint",
    "clearance_result_fingerprint",
    "DOMAIN_SIGNAL_CONTENT",
    "DOMAIN_SIGNAL_PROVENANCE",
    "DOMAIN_SIGNAL_BUNDLE",
    "DOMAIN_ACTION",
    "DOMAIN_REQUEST",
    "DOMAIN_RESULT",
]
