"""Version compatibility (Phase 14). A pinned version set per trace, with explicit
backward-compatible reads and forward-incompatible rejection. No silent coercion across
incompatible MAJOR versions. Missing/unknown version => fail-closed.

Each dimension carries (name -> supported majors). A consumer supports a set of majors; a
producer emits one. Compatible iff producer major ∈ consumer.supported. Minor differences within
a supported major are backward-compatible reads; a higher unsupported major is forward-
incompatible and rejected (never coerced).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# current pinned versions for the shadow pilot
PINNED = {
    "envelope": "1", "contracts": "1", "adapter": "shadow_adapter_v1", "policy": "policy_v1",
    "registry": "reg_v1", "tap": "tap_e4_governance_F", "action_gate": "action_gate_ref_v1",
    "audit": "control_plane_audit_v1", "vocabulary": "gov_vocab_v1",
}

# supported majors per dimension (consumer side). A single-element set = strict.
SUPPORTED = {
    "envelope": {"1"}, "contracts": {"1"}, "policy": {"policy_v1"}, "registry": {"reg_v1"},
    "tap": {"tap_e4_governance_F"}, "action_gate": {"action_gate_ref_v1"},
    "audit": {"control_plane_audit_v1"}, "vocabulary": {"gov_vocab_v1"},
}


@dataclass
class CompatResult:
    dimension: str
    producer: Optional[str]
    ok: bool
    kind: str            # OK | BACKWARD_COMPAT | FORWARD_INCOMPATIBLE | MISSING | UNKNOWN
    reason_code: Optional[str] = None


def _major(v: str) -> str:
    return v


def check(dimension: str, producer: Optional[str]) -> CompatResult:
    supported = SUPPORTED.get(dimension)
    if supported is None:
        return CompatResult(dimension, producer, False, "UNKNOWN", "POLICY.CONTRACT_VERSION_UNSUPPORTED")
    if producer is None:
        return CompatResult(dimension, producer, False, "MISSING", "POLICY.CONTRACT_VERSION_UNSUPPORTED")
    if producer in supported:
        return CompatResult(dimension, producer, True, "OK")
    # not supported: forward-incompatible; NEVER silently coerced
    code = {"policy": "POLICY.POLICY_VERSION_MISMATCH", "registry": "POLICY.REGISTRY_VERSION_MISMATCH"
            }.get(dimension, "POLICY.CONTRACT_VERSION_UNSUPPORTED")
    return CompatResult(dimension, producer, False, "FORWARD_INCOMPATIBLE", code)


def check_envelope(env: Dict) -> List[CompatResult]:
    return [
        check("envelope", env.get("envelope_version")),
        check("registry", env.get("registry_version")),
        check("policy", ("policy_v1" if env.get("policy_versions", {}).get("assertion") == "v1" else
                         env.get("policy_versions", {}).get("assertion"))),
    ]


def first_incompatible(env: Dict) -> Optional[CompatResult]:
    for r in check_envelope(env):
        if not r.ok:
            return r
    return None


def matrix() -> Dict[str, Dict[str, str]]:
    """The full compatibility matrix as data (for the doc + tests)."""
    out = {}
    for dim, sup in SUPPORTED.items():
        out[dim] = {"pinned": PINNED.get(dim, ""), "supported": sorted(sup),
                    "on_mismatch": check(dim, "SOME_OTHER_MAJOR").reason_code,
                    "on_missing": "fail-closed POLICY.CONTRACT_VERSION_UNSUPPORTED"}
    return out
