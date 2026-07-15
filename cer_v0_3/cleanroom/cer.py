"""Clean-room CER validation, normalization, and action identity.

Independent reimplementation from the published CER V0.2 specification and JSON
Schema. Given a CER object it exposes:

  * ``validate(cer)``            — structural + profile validation (fail closed);
  * ``normalized_payload(cer)``  — the v2 identity projection (provenance excluded);
  * ``canonical_bytes(cer)``     — JCS+Action-Profile canonical bytes of that payload;
  * ``action_digest(cer)``       — the hex action identity.

Identity = SHA-256 over the domain-separated, length-prefixed canonical bytes of
the v2-projected universal envelope. Provenance (runtime, model_provider,
objective) is EXCLUDED from identity. Profiles are domain-separated by
``tool.tool_name`` inside the hashed payload.

Imports: standard library + this clean-room package only. No reference code.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet

from . import canon, digest, profiles
from .errors import (
    CERSchemaError,
    MissingFieldError,
    OperationMismatchError,
    ProhibitedFieldError,
    UnknownFieldError,
    UnknownProfileError,
    UnsupportedExtensionError,
)

CER_VERSION = "0.2"
SET_PATHS: FrozenSet[str] = frozenset({"credential_scope.permissions"})

_ALLOWED_TOP = {"cer_version", "profile", "risk_tier", "authority", "state_binding",
                "policy_ref", "actuation", "provenance", "extensions"}
_REQUIRED_TOP = ("cer_version", "profile", "authority", "state_binding", "policy_ref",
                 "actuation")


def _check_actuation_fields(actuation: Dict[str, Any], prof) -> None:
    for f in prof.required:
        if f not in actuation or actuation[f] is None:
            raise MissingFieldError(f"actuation.{f} required for {prof.profile_id}",
                                    path=f"actuation.{f}")
    for f in prof.prohibited:
        if f in actuation:
            raise ProhibitedFieldError(
                f"prohibited field {f!r} present for {prof.profile_id} "
                "(profile downgrade/confusion)", path=f"actuation.{f}")
    allowed = set(prof.required) | set(prof.optional)
    unknown = set(actuation) - allowed
    if unknown:
        raise UnknownFieldError(
            f"unknown actuation field(s) for {prof.profile_id}: {sorted(unknown)}",
            path="actuation")


def validate(cer: Dict[str, Any]) -> None:
    """Fail closed on any structural / profile / extension / downgrade violation."""
    if not isinstance(cer, dict):
        raise CERSchemaError("CER must be a JSON object")
    if cer.get("cer_version") != CER_VERSION:
        raise CERSchemaError(f"unsupported cer_version {cer.get('cer_version')!r}")
    unknown = set(cer) - _ALLOWED_TOP
    if unknown:
        raise UnknownFieldError(f"unsupported top-level key(s): {sorted(unknown)}")
    for f in _REQUIRED_TOP:
        if f not in cer or cer[f] is None:
            raise MissingFieldError(f"missing required field {f}", path=f)

    prof = profiles.get(cer["profile"])
    if prof is None:
        raise UnknownProfileError(f"unknown profile {cer['profile']!r}")

    auth = cer["authority"]
    for f in ("principal", "permissions"):
        if f not in auth:
            raise MissingFieldError(f"authority.{f} required", path=f"authority.{f}")
    sb = cer["state_binding"]
    for f in ("resource_version", "state_hash", "as_of", "operational"):
        if f not in sb:
            raise MissingFieldError(f"state_binding.{f} required", path=f"state_binding.{f}")
    if "version" not in cer["policy_ref"]:
        raise MissingFieldError("policy_ref.version required", path="policy_ref.version")

    actuation = cer["actuation"]
    if actuation.get("operation") != prof.operation:
        raise OperationMismatchError(
            f"actuation.operation {actuation.get('operation')!r} inconsistent with "
            f"profile {prof.profile_id} (expected {prof.operation})", path="actuation.operation")

    _check_actuation_fields(actuation, prof)
    prof.validate_extra(actuation)

    ext = cer.get("extensions")
    if ext not in (None, {}) and (not isinstance(ext, dict) or ext):
        raise UnsupportedExtensionError(
            f"unsupported extension(s): "
            f"{sorted(ext) if isinstance(ext, dict) else ext!r}", path="extensions")


def normalized_payload(cer: Dict[str, Any]) -> Dict[str, Any]:
    """The v2 identity projection (provenance-excluded) — the object that is hashed.

    Built as: universal-envelope construction (from the CER + profile mapping) ->
    v2 projection (drop runtime/model_provider/objective/action_id/timestamp/sig/
    approvals/attestation). Key set and values match the published projection.
    """
    validate(cer)
    prof = profiles.get(cer["profile"])
    auth = cer["authority"]
    sb = cer["state_binding"]
    pol = cer["policy_ref"]
    actuation = cer["actuation"]
    principal = auth["principal"]
    target_id = prof.target_id(actuation)

    payload: Dict[str, Any] = {
        "agent_identity": {"id": principal, "key_id": auth.get("key_id", "cer-key")},
        "delegator": auth.get("delegator", {"id": principal, "type": "SERVICE"}),
        "delegation_chain": auth.get("delegation_chain", [{"grant": "*"}]),
        "tool": {"server_id": prof.server_id, "tool_name": prof.tool_name},
        "operation": actuation["operation"],
        "target_resource": [target_id],
        "arguments": dict(prof.arguments(actuation)),
        "credential_scope": {"principal": principal, "permissions": list(auth["permissions"])},
        "current_state_hash": sb["state_hash"],
        "state_freshness": {"as_of": sb["as_of"],
                            "source": sb.get("source", prof.freshness_source)},
        "reversibility": actuation["reversibility"],
        "policy_version": pol["version"],
        "correlation_id": sb.get("correlation_id", target_id),
        "sequence_id": str(sb.get("sequence_id", "1")),
    }
    rb = prof.rollback_plan(actuation)
    if rb is not None:
        payload["rollback_plan"] = rb
    return payload


def canonical_bytes(cer: Dict[str, Any]) -> bytes:
    return canon.canonical_bytes(normalized_payload(cer), SET_PATHS)


def action_digest(cer: Dict[str, Any]) -> str:
    return digest.action_digest(canonical_bytes(cer))
