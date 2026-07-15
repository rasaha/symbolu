"""Canonical Execution Request (CER) V0.1 — narrowly scoped reference.

Scope (frozen for this milestone): one shared actuation surface, ``kubernetes.scale``.
The CER is the runtime-facing object; its *identity* is grounded in the frozen
ActionGate canonicalization + hashing under identity-profile **v2** (provenance
excluded). This module does three deterministic things and nothing else:

  1. ``validate_cer``      — structural validation of a CER V0.1 object.
  2. ``to_envelope``       — deterministic CER -> ActionGate action envelope.
  3. ``action_digest``     — the CER identity = ActionGate v2 action_hash of (2).
  plus CER -> ACP CloudWorldState / CloudActionCandidate for the operational layer.

Design rule (identity vs provenance)
------------------------------------
Identity-bearing fields DEFINE the exact requested actuation: operation, actuation
interface, target, arguments, requested state transition, authority binding,
external-state binding, policy reference, reversibility. Provenance fields are
retained for audit but MUST NOT affect the digest: runtime, runtime_version,
model_provider, model, planner, objective, reasoning_trace_ref, adapter_version,
explanation. This mirrors ActionGate identity-profile v2 exactly.

Determinism: no wall clock, no randomness. All timestamps/ids come from the input
CER (or fixed identity-excluded constants), so reruns are byte-identical.
"""
from __future__ import annotations

from typing import Any, Dict

from . import _paths  # noqa: F401  (sys.path bootstrap)
from action_gate_ref import projection  # noqa: E402

CER_VERSION = "0.1"
PROFILE = "cer.k8s.scale/0.1"
IDENTITY_PROFILE = "v2"  # the provenance-excluded ActionGate identity

# action_id/timestamp/sequence are identity-EXCLUDED (v2 base exclusions), so fixed
# deterministic values keep reruns byte-identical without affecting the digest.
_FIXED_ACTION_ID = "00000000-0000-4000-8000-000000000000"

# The nine identity-bearing top-level CER identity fields.
IDENTITY_FIELDS = (
    "operation", "actuation_interface", "target", "arguments",
    "requested_state_transition", "authority", "external_state_binding",
    "policy_ref", "reversibility",
)
# Provenance fields (retained for audit, excluded from identity).
PROVENANCE_FIELDS = (
    "runtime", "runtime_version", "model_provider", "model", "planner",
    "objective", "reasoning_trace_ref", "adapter_version", "explanation",
)


class CERValidationError(ValueError):
    """Raised on a structurally invalid CER (fail closed)."""


def _req(d: Dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d or d[key] is None:
        raise CERValidationError(f"missing required field {ctx}.{key}")
    return d[key]


def validate_cer(cer: Dict[str, Any]) -> None:
    """Structural validation. Raises CERValidationError on any violation."""
    if not isinstance(cer, dict):
        raise CERValidationError("CER must be a JSON object")
    if cer.get("cer_version") != CER_VERSION:
        raise CERValidationError(f"unsupported cer_version {cer.get('cer_version')!r}")
    if cer.get("profile") != PROFILE:
        # unknown profile -> fail closed (spec: UNSUPPORTED_PROFILE)
        raise CERValidationError(f"unsupported profile {cer.get('profile')!r}")
    ident = _req(cer, "identity", "cer")
    for f in IDENTITY_FIELDS:
        _req(ident, f, "identity")
    # actuation interface is the shared surface — pinned in V0.1
    if ident["actuation_interface"] != "kubernetes.scale":
        raise CERValidationError(
            f"V0.1 pins actuation_interface=kubernetes.scale, got {ident['actuation_interface']!r}")
    tgt = ident["target"]
    for f in ("cluster", "namespace", "deployment"):
        _req(tgt, f, "identity.target")
    st = ident["requested_state_transition"]
    _req(st, "replicas", "identity.requested_state_transition")
    # extensions must be declared; unknown top-level keys fail closed
    allowed_top = {"cer_version", "profile", "identity", "provenance", "evidence",
                   "risk_tier", "extensions"}
    unknown = set(cer) - allowed_top
    if unknown:
        raise CERValidationError(f"unsupported extension keys: {sorted(unknown)}")
    ext = cer.get("extensions")
    if ext not in (None, {}) and not isinstance(ext, dict):
        raise CERValidationError("extensions must be an object")
    # unsupported (non-empty, unrecognized) extension -> fail closed
    if isinstance(ext, dict) and ext:
        raise CERValidationError(f"unsupported extension(s): {sorted(ext)}")


def to_envelope(cer: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic CER -> ActionGate canonical action envelope.

    Provenance -> runtime/model_provider/objective (present for audit; excluded
    from the v2 identity). Identity -> the authorization-relevant envelope fields.
    """
    validate_cer(cer)
    ident = cer["identity"]
    prov = cer.get("provenance", {})
    tgt = ident["target"]
    target_id = f"{tgt['namespace']}/{tgt['deployment']}"
    esb = ident["external_state_binding"]
    auth = ident["authority"]
    pol = ident["policy_ref"]
    st = ident["requested_state_transition"]["replicas"]

    envelope: Dict[str, Any] = {
        "action_id": _FIXED_ACTION_ID,
        "timestamp": esb["as_of"],
        "agent_identity": {
            "id": auth["principal"], "key_id": auth.get("key_id", "cer-key"), "sig": "cer",
        },
        # --- provenance (identity-excluded under v2) ---
        "runtime": prov.get("runtime", "unknown"),
        "model_provider": {
            "model": prov.get("model", ""), "provider": prov.get("model_provider", ""),
        },
        "objective": prov.get("objective", ""),
        # --- identity-bearing ---
        "delegator": auth.get("delegator", {"id": auth["principal"], "type": "SERVICE"}),
        "delegation_chain": auth.get("delegation_chain", [{"grant": "*"}]),
        "tool": {"server_id": "kubernetes", "tool_name": "scale"},
        "operation": ident["operation"],
        "target_resource": [target_id],
        "arguments": dict(ident["arguments"]),
        "credential_scope": {
            "principal": auth["principal"], "permissions": list(auth["permissions"]),
        },
        "current_state_hash": esb["state_hash"],
        "state_freshness": {"as_of": esb["as_of"], "source": esb.get("source", "kubernetes")},
        "policy_version": pol["version"],
        "reversibility": ident["reversibility"],
        # correlation_id/sequence_id define this exact requested actuation for BOTH
        # runtimes: they are carried from the shared actuation request, so the same
        # logical action correlates identically (NOT excluded to force a match).
        "correlation_id": esb.get("correlation_id", target_id),
        "sequence_id": str(esb.get("sequence_id", "1")),
    }
    return envelope


def action_digest(cer: Dict[str, Any], *, algorithm_id: str = "sha-256") -> str:
    """The CER identity: the ActionGate v2 action_hash of its derived envelope.

    By construction, ``same actuation -> same digest`` and provenance differences
    do NOT change it (v2 excludes runtime/model_provider/objective), while any
    identity-bearing change DOES.
    """
    env = to_envelope(cer)
    return projection.action_hash(
        env, algorithm_id=algorithm_id, identity_profile=IDENTITY_PROFILE)


# --------------------------------------------------------------------------- #
# CER -> ACP cloud envelopes (operational-safety layer)
# --------------------------------------------------------------------------- #

def _world_for(cer: Dict[str, Any], resource_version: str):
    """Build a CloudWorldState at a given resource_version (for identity/binding)."""
    from symbolu_robotics.autonomous_control_plane.cloud.envelopes import CloudWorldState
    ident = cer["identity"]
    tgt = ident["target"]
    esb = ident["external_state_binding"]
    op = esb["operational"]
    return CloudWorldState(
        cluster=tgt["cluster"], namespace=tgt["namespace"], deployment=tgt["deployment"],
        resource_version=resource_version,
        generation=int(op["generation"]),
        desired_replicas=int(op["desired_replicas"]),
        current_replicas=int(op["current_replicas"]),
        available_replicas=int(op["available_replicas"]),
        readiness_plasticity=float(op["readiness_plasticity"]),
        active_rollback_watches=int(op["active_rollback_watches"]),
        seconds_since_last_action=float(op["seconds_since_last_action"]),
        dependency_healthy=bool(op["dependency_healthy"]),
        freeze_active=bool(op["freeze_active"]),
        observation_time_s=float(op["observation_time_s"]),
    )


def to_cloud_world(cer: Dict[str, Any]):
    """CER external-state binding -> ACP CloudWorldState (LIVE-state model).

    ``live_resource_version`` (if present) models a cluster whose state advanced
    after the runtime observed it (TOCTOU); otherwise the live state equals the
    observed binding (fresh).
    """
    from symbolu_robotics.autonomous_control_plane.cloud.envelopes import CloudWorldState
    ident = cer["identity"]
    tgt = ident["target"]
    esb = ident["external_state_binding"]
    op = esb["operational"]
    live_rv = esb.get("live_resource_version", esb["resource_version"])
    return CloudWorldState(
        cluster=tgt["cluster"], namespace=tgt["namespace"], deployment=tgt["deployment"],
        resource_version=live_rv,
        generation=int(op["generation"]),
        desired_replicas=int(op["desired_replicas"]),
        current_replicas=int(op["current_replicas"]),
        available_replicas=int(op["available_replicas"]),
        readiness_plasticity=float(op["readiness_plasticity"]),
        active_rollback_watches=int(op["active_rollback_watches"]),
        seconds_since_last_action=float(op["seconds_since_last_action"]),
        dependency_healthy=bool(op["dependency_healthy"]),
        freeze_active=bool(op["freeze_active"]),
        observation_time_s=float(op["observation_time_s"]),
    )


def to_cloud_candidate(cer: Dict[str, Any]):
    """CER requested transition -> ACP CloudActionCandidate (SCALE)."""
    from symbolu_robotics.autonomous_control_plane.cloud.envelopes import (
        CloudActionCandidate, CloudOperation,
    )
    ident = cer["identity"]
    tgt = ident["target"]
    esb = ident["external_state_binding"]
    st = ident["requested_state_transition"]["replicas"]
    return CloudActionCandidate(
        candidate_id="cand:scale",
        operation=CloudOperation.SCALE,
        namespace=tgt["namespace"], deployment=tgt["deployment"],
        current_replicas=int(st["from"]),
        desired_replicas=int(st["to"]),
        manifest_digest="",
        rollback_ref=esb.get("rollback_ref", ""),
        rollout_strategy="RollingUpdate",
        max_unavailable=0, max_surge=1, timeout_s=60.0,
        # The candidate binds to the identity of the state the runtime OBSERVED.
        # When live == observed (fresh) this equals to_cloud_world().version and
        # the ACP binding holds; when the live cluster advanced (stale) it differs
        # and ACP fails closed (STATE_BINDING_MISMATCH).
        origin_state_version=_world_for(cer, esb["resource_version"]).version,
    )
