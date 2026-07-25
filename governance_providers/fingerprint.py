"""Deterministic result fingerprints (kernel-free).

A stable SHA-256 over the canonical (sorted-key) JSON of a mapping — used by
providers to publish a reproducible result fingerprint the conformance kit can
assert on.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping


def fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
