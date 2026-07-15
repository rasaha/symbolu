"""Domain-neutral universal-envelope construction for CER V0.3 profiles.

Generalizes the V0.2 ``_common.build_envelope`` so a non-Kubernetes profile
(e.g. ``database.mutation.v1``) does NOT inherit Kubernetes terminology: the
``tool.server_id`` and ``state_freshness.source`` are parameters, not the constant
``"kubernetes"``. The projected identity fields and their shapes are otherwise
identical to V0.2, so the V0.2 profiles keep their exact digests (they are NOT
routed through here — they stay frozen in ``cer_v0_2``).

Provenance (runtime, model_provider, objective) is written into the envelope for
audit but excluded from identity by the frozen ActionGate v2 projection.
"""
from __future__ import annotations

from typing import Any, Dict

_FIXED_ACTION_ID = "00000000-0000-4000-8000-000000000000"


def build_envelope(cer: Dict[str, Any], *, server_id: str, tool_name: str,
                   operation: str, target_id: str, arguments: Dict[str, Any],
                   reversibility: str, freshness_source: str,
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
        "tool": {"server_id": server_id, "tool_name": tool_name},
        "operation": operation,
        "target_resource": [target_id],
        "arguments": dict(arguments),
        "credential_scope": {"principal": auth["principal"],
                             "permissions": list(auth["permissions"])},
        "current_state_hash": sb["state_hash"],
        "state_freshness": {"as_of": sb["as_of"],
                            "source": sb.get("source", freshness_source)},
        "policy_version": pol["version"],
        "reversibility": reversibility,
        "correlation_id": sb.get("correlation_id", target_id),
        "sequence_id": str(sb.get("sequence_id", "1")),
    }
    if rollback_plan is not None:
        env["rollback_plan"] = rollback_plan
    return env
