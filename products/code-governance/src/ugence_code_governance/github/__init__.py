"""Read-only GitHub evidence connector (product; owns no governance authority).

Fixture-backed / supplied-payload only. No write calls, no network calls, no
merge credentials. This is the connector referenced by the readiness audit's
Product-Package Boundary; it emits neutral product records, never mutations.
"""
from __future__ import annotations

from .normalizer import SUPPORTED_PULL_REQUEST_ACTIONS, normalize_pull_request_event
from .webhook import compute_signature, verify_signature

__all__ = [
    "normalize_pull_request_event",
    "SUPPORTED_PULL_REQUEST_ACTIONS",
    "compute_signature",
    "verify_signature",
]
