"""Identity bridge — proves exact-action continuity across the boundary.

The CER identity the runtime computes before submission MUST equal the identity the
control plane reports. Any material change to the action yields a new identity; a
provenance-only change does not. This module is where the runtime asserts those
properties (via the frozen contract) — it never computes authorization.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

from .cer_builder import cer_identity


def same_identity(cer_a: Dict[str, Any], cer_b: Dict[str, Any]) -> bool:
    return cer_identity(cer_a) == cer_identity(cer_b)


def provenance_variant(cer: Dict[str, Any], provenance: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with different provenance (must keep the same identity)."""
    out = copy.deepcopy(cer)
    out["provenance"] = dict(provenance)
    return out


def assert_binding(cer: Dict[str, Any], expected_identity: str) -> None:
    """Fail closed if the CER no longer binds to the expected identity."""
    actual = cer_identity(cer)
    if actual != expected_identity:
        from ..contracts.errors import GovernanceBoundaryError
        raise GovernanceBoundaryError(
            f"CER identity changed ({actual[:12]} != {expected_identity[:12]}); "
            "a modified action invalidates a prior decision")
