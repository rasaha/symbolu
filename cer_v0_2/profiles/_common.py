"""Shared CER V0.2 -> ActionGate envelope construction.

The mapping is byte-identical in shape to CER V0.1's ``to_envelope`` so that
``kubernetes.scale.v1`` yields the SAME action identity as V0.1 for the same
actuation. Profiles differ ONLY in ``tool.tool_name`` (the domain separator),
``arguments``, ``reversibility``, and optional ``rollback_plan`` — all inside the
hashed payload, so profiles never collide.
"""
from __future__ import annotations

from typing import Any, Dict

_FIXED_ACTION_ID = "00000000-0000-4000-8000-000000000000"


def build_envelope(cer: Dict[str, Any], *, tool_name: str, operation: str,
                   target_id: str, arguments: Dict[str, Any], reversibility: str,
                   rollback_plan: Any = None) -> Dict[str, Any]:
    auth = cer["authority"]
    sb = cer["state_binding"]
    pol = cer["policy_ref"]
    prov = cer.get("provenance", {})
    env: Dict[str, Any] = {
        "action_id": _FIXED_ACTION_ID,
        "timestamp": sb["as_of"],
        "agent_identity": {"id": auth["principal"], "key_id": auth.get("key_id", "cer-key"),
                           "sig": "cer"},
        # provenance (identity-excluded under ActionGate v2)
        "runtime": prov.get("runtime", "unknown"),
        "model_provider": {"model": prov.get("model", ""),
                           "provider": prov.get("model_provider", "")},
        "objective": prov.get("objective", ""),
        # identity-bearing
        "delegator": auth.get("delegator", {"id": auth["principal"], "type": "SERVICE"}),
        "delegation_chain": auth.get("delegation_chain", [{"grant": "*"}]),
        "tool": {"server_id": "kubernetes", "tool_name": tool_name},
        "operation": operation,
        "target_resource": [target_id],
        "arguments": dict(arguments),
        "credential_scope": {"principal": auth["principal"],
                             "permissions": list(auth["permissions"])},
        "current_state_hash": sb["state_hash"],
        "state_freshness": {"as_of": sb["as_of"], "source": sb.get("source", "kubernetes")},
        "policy_version": pol["version"],
        "reversibility": reversibility,
        "correlation_id": sb.get("correlation_id", target_id),
        "sequence_id": str(sb.get("sequence_id", "1")),
    }
    if rollback_plan is not None:
        env["rollback_plan"] = rollback_plan
    return env


def cloud_world(cer: Dict[str, Any], resource_version: str):
    from symbolu_robotics.autonomous_control_plane.cloud.envelopes import CloudWorldState
    act = cer["actuation"]
    tgt = act["target"]
    op = cer["state_binding"]["operational"]
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


def live_cloud_world(cer: Dict[str, Any]):
    sb = cer["state_binding"]
    return cloud_world(cer, sb.get("live_resource_version", sb["resource_version"]))


def observed_world_version(cer: Dict[str, Any]) -> str:
    return cloud_world(cer, cer["state_binding"]["resource_version"]).version
