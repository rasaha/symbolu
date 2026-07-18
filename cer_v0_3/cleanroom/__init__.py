"""CER V0.3 clean-room reference implementation.

An INDEPENDENT implementation of the CER canonicalization, v2 identity projection,
and action-digest, written from the published specification and JSON Schema. It
imports only the Python standard library and this package — never the reference
ActionGate code (``action_gate_ref``), the CER V0.1/V0.2 packages, or the ACP
(``symbolu_robotics``). Enforced by ``tests/test_forbidden_imports.py``.

Public surface:
    validate(cer)             -> None (raises CleanRoomError on any violation)
    normalized_payload(cer)   -> dict (v2 identity projection)
    canonical_bytes(cer)      -> bytes (JCS + Action Profile)
    action_digest(cer)        -> str  (hex identity)
"""
from __future__ import annotations

from .cer import action_digest, canonical_bytes, normalized_payload, validate
from .errors import CleanRoomError

__all__ = ["validate", "normalized_payload", "canonical_bytes", "action_digest",
           "CleanRoomError"]
