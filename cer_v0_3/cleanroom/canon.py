"""Clean-room JCS (RFC-8785) + Action-Profile canonicalizer — extracted.

The implementation formerly resident in this module now lives in the independently
installable, standard-library-only, authority-neutral leaf distribution
``ugence-jcs`` (``packages/jcs``). This module re-exports it so the clean-room
surface, its byte stream, and every frozen CER V0.2 identity digest are unchanged.

The extraction preserves clean-room independence: ``ugence_jcs`` imports only the
Python standard library and shares no code with the reference path
(``action_gate_ref``, ``cer_v0_2``, ``cer_v0_1``, ``symbolu_robotics``). That is
enforced by ``tests/test_forbidden_imports.py``, which permits exactly this one
first-party import and re-proves that ``ugence_jcs`` is itself stdlib-only.
"""
from __future__ import annotations

from ugence_jcs.canon import canonical_bytes, canonical_string

__all__ = ["canonical_string", "canonical_bytes"]
