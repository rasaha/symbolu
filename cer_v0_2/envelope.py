"""CER V0.2 — universal envelope + domain profiles.

The envelope is profile-independent: cer_version, profile, authority, state_binding,
policy_ref, actuation (profile-specific), provenance, extensions. Identity is the
ActionGate v2 action_hash of the profile's envelope projection; profiles are
domain-separated by ``tool.tool_name`` (inside the hash). Provenance never enters
the identity.
"""
from __future__ import annotations

from typing import Any, Dict

from . import _paths  # noqa: F401
from .profiles import get_profile
from .profiles.base import CERValidationError
from action_gate_ref import projection  # noqa: E402

CER_VERSION = "0.2"
IDENTITY_PROFILE = "v2"  # ActionGate identity profile (provenance-excluded)

_ALLOWED_TOP = {"cer_version", "profile", "risk_tier", "authority", "state_binding",
                "policy_ref", "actuation", "provenance", "extensions"}
_REQUIRED_TOP = ("cer_version", "profile", "authority", "state_binding", "policy_ref",
                 "actuation")


def validate_cer(cer: Dict[str, Any]) -> None:
    """Structural validation. Fail closed on unknown profile/extension/downgrade."""
    if not isinstance(cer, dict):
        raise CERValidationError("CER must be a JSON object")
    if cer.get("cer_version") != CER_VERSION:
        raise CERValidationError(f"unsupported cer_version {cer.get('cer_version')!r}")
    unknown = set(cer) - _ALLOWED_TOP
    if unknown:
        raise CERValidationError(f"unsupported top-level key(s): {sorted(unknown)}")
    for f in _REQUIRED_TOP:
        if f not in cer or cer[f] is None:
            raise CERValidationError(f"missing required field {f}")
    prof = get_profile(cer["profile"])  # unknown profile -> fail closed
    # authority
    auth = cer["authority"]
    for f in ("principal", "permissions"):
        if f not in auth:
            raise CERValidationError(f"authority.{f} required")
    # state binding
    sb = cer["state_binding"]
    for f in ("resource_version", "state_hash", "as_of", "operational"):
        if f not in sb:
            raise CERValidationError(f"state_binding.{f} required")
    # policy ref
    if "version" not in cer["policy_ref"]:
        raise CERValidationError("policy_ref.version required")
    # actuation operation must match the profile's ActionGate operation
    if cer["actuation"].get("operation") != prof.ACTIONGATE_OPERATION:
        raise CERValidationError(
            f"actuation.operation {cer['actuation'].get('operation')!r} inconsistent with "
            f"profile {cer['profile']} (expected {prof.ACTIONGATE_OPERATION})")
    # profile-specific actuation (required/optional/prohibited)
    prof.validate_actuation(cer["actuation"])
    # extensions: non-empty unrecognized -> fail closed
    ext = cer.get("extensions")
    if ext not in (None, {}) and (not isinstance(ext, dict) or ext):
        raise CERValidationError(f"unsupported extension(s): "
                                 f"{sorted(ext) if isinstance(ext, dict) else ext!r}")


def to_envelope(cer: Dict[str, Any]) -> Dict[str, Any]:
    validate_cer(cer)
    return get_profile(cer["profile"]).to_envelope(cer)


def action_digest(cer: Dict[str, Any], *, algorithm_id: str = "sha-256") -> str:
    """CER V0.2 identity = ActionGate v2 action_hash of the profile's envelope."""
    env = to_envelope(cer)
    return projection.action_hash(env, algorithm_id=algorithm_id,
                                  identity_profile=IDENTITY_PROFILE)


def to_cloud_world(cer: Dict[str, Any]):
    validate_cer(cer)
    return get_profile(cer["profile"]).to_cloud_world(cer)


def to_cloud_candidate(cer: Dict[str, Any]):
    validate_cer(cer)
    return get_profile(cer["profile"]).to_cloud_candidate(cer)
