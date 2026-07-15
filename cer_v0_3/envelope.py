"""CER V0.3 envelope (original side) — universal envelope across three domains.

Dispatches by profile:
  * ``kubernetes.scale.v1`` / ``kubernetes.rollout.v1`` -> frozen ``cer_v0_2`` (unchanged);
  * ``database.mutation.v1`` -> the new V0.3 database profile.

Identity is the ActionGate v2 ``action_hash`` of the profile's envelope projection,
exactly as in V0.2. Provenance never enters identity. Unknown profiles fail closed.
"""
from __future__ import annotations

from typing import Any, Dict

from . import _paths  # noqa: F401
from .profiles import get_profile as _v3_profile
from .profiles.base import CERValidationError
from action_gate_ref import projection  # noqa: E402

from cer_v0_2 import envelope as _v2  # frozen K8s profiles  # noqa: E402

CER_VERSION = "0.2"          # V0.3 keeps the V0.2 CER envelope version (additive profile)
IDENTITY_PROFILE = "v2"

_V2_PROFILES = {"kubernetes.scale.v1", "kubernetes.rollout.v1"}

_ALLOWED_TOP = {"cer_version", "profile", "risk_tier", "authority", "state_binding",
                "policy_ref", "actuation", "provenance", "extensions"}
_REQUIRED_TOP = ("cer_version", "profile", "authority", "state_binding", "policy_ref",
                 "actuation")


def _validate_v3(cer: Dict[str, Any]) -> None:
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
    prof = _v3_profile(cer["profile"])
    if prof is None:
        raise CERValidationError(f"unsupported profile {cer['profile']!r} (fail closed)")
    auth = cer["authority"]
    for f in ("principal", "permissions"):
        if f not in auth:
            raise CERValidationError(f"authority.{f} required")
    sb = cer["state_binding"]
    for f in ("resource_version", "state_hash", "as_of", "operational"):
        if f not in sb:
            raise CERValidationError(f"state_binding.{f} required")
    if "version" not in cer["policy_ref"]:
        raise CERValidationError("policy_ref.version required")
    if cer["actuation"].get("operation") != prof.ACTIONGATE_OPERATION:
        raise CERValidationError(
            f"actuation.operation {cer['actuation'].get('operation')!r} inconsistent with "
            f"profile {cer['profile']} (expected {prof.ACTIONGATE_OPERATION})")
    prof.validate_actuation(cer["actuation"])
    ext = cer.get("extensions")
    if ext not in (None, {}) and (not isinstance(ext, dict) or ext):
        raise CERValidationError(
            f"unsupported extension(s): {sorted(ext) if isinstance(ext, dict) else ext!r}")


def _profile_id(cer: Dict[str, Any]) -> Any:
    return cer.get("profile") if isinstance(cer, dict) else None


def validate_cer(cer: Dict[str, Any]) -> None:
    if _profile_id(cer) in _V2_PROFILES:
        return _v2.validate_cer(cer)
    _validate_v3(cer)


def to_envelope(cer: Dict[str, Any]) -> Dict[str, Any]:
    if _profile_id(cer) in _V2_PROFILES:
        return _v2.to_envelope(cer)
    _validate_v3(cer)
    return _v3_profile(cer["profile"]).to_envelope(cer)


def action_digest(cer: Dict[str, Any], *, algorithm_id: str = "sha-256") -> str:
    if _profile_id(cer) in _V2_PROFILES:
        return _v2.action_digest(cer, algorithm_id=algorithm_id)
    env = to_envelope(cer)
    return projection.action_hash(env, algorithm_id=algorithm_id,
                                  identity_profile=IDENTITY_PROFILE)
