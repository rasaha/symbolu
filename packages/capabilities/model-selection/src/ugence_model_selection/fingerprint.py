"""Deterministic result fingerprints (dependency-free).

A stable SHA-256 over the canonical (sorted-key) JSON of a mapping — used to publish a
reproducible fingerprint of an eligibility decision or a selection result for audit and
replay. This adds NO new selection behaviour: it hashes an already-produced record (e.g.
``EligibilityDecision.to_dict()``), it does not change how eligibility or selection is
computed.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping


def fingerprint(payload: Mapping[str, object]) -> str:
    """Stable SHA-256 over canonical JSON of ``payload`` (sorted keys, compact)."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
