"""Profile contract for CER V0.2 (universal envelope + domain profiles).

A profile defines its identity-bearing / optional / prohibited actuation fields,
argument normalization, the ActionGate envelope projection, and the ACP cloud
mapping. The universal envelope (authority, state_binding, policy_ref, provenance,
extensions) is profile-independent. Unknown profiles fail closed.

Design invariants:
* the CER profile maps 1:1 to a distinct ActionGate ``tool.tool_name`` and to a
  distinct actuation payload, so two profiles CANNOT produce the same action
  digest (domain separation via the tool field, which is inside the hash);
* provenance never enters the action identity;
* scale.v1's envelope projection is byte-identical to CER V0.1's (frozen).
"""
from __future__ import annotations

from typing import Any, Dict, Protocol


class CERValidationError(ValueError):
    """Structurally invalid CER (fail closed)."""


class Profile(Protocol):
    PROFILE_ID: str
    ACTIONGATE_TOOL: str            # tool.tool_name — the domain separator
    ACTIONGATE_OPERATION: str
    REQUIRED_ACTUATION: tuple
    OPTIONAL_ACTUATION: tuple
    PROHIBITED_ACTUATION: tuple

    def validate_actuation(self, actuation: Dict[str, Any]) -> None: ...
    def to_envelope(self, cer: Dict[str, Any]) -> Dict[str, Any]: ...
    def to_cloud_world(self, cer: Dict[str, Any]): ...
    def to_cloud_candidate(self, cer: Dict[str, Any]): ...


def _require(d: Dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d or d[key] is None:
        raise CERValidationError(f"missing required field {ctx}.{key}")
    return d[key]


def check_fields(actuation: Dict[str, Any], required, optional, prohibited, profile_id: str) -> None:
    """Shared field-presence enforcement (fail closed)."""
    for f in required:
        _require(actuation, f, f"actuation[{profile_id}]")
    # prohibited fields (e.g., rollout-only fields under scale) -> profile downgrade
    for f in prohibited:
        if f in actuation:
            raise CERValidationError(
                f"prohibited field {f!r} present for profile {profile_id} "
                "(possible profile downgrade/confusion)")
    allowed = set(required) | set(optional)
    unknown = set(actuation) - allowed
    if unknown:
        raise CERValidationError(
            f"unknown actuation field(s) for {profile_id}: {sorted(unknown)}")
