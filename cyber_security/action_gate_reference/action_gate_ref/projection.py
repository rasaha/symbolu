"""Action-hash projection: the exact inclusion/exclusion rules (spec §10).

Included: authorization-relevant fields. Excluded (justified): action_id,
timestamp, agent_identity.sig, approvals, attestation. Included-by-digest:
expected_effects -> expected_effects_digest (SIMULATION domain).
"""

from __future__ import annotations

from typing import Any

from . import canon_profile as cp
from . import hashing, jcs
from .schema import ENVELOPE_SET_PATHS

# machine-readable projection manifest (spec §10)
PROJECTION_MANIFEST = {
    "canonicalization_version": cp.CANONICALIZATION_VERSION,
    "envelope_schema_version": cp.ENVELOPE_SCHEMA_VERSION,
    "included": [
        "agent_identity.id", "agent_identity.key_id", "runtime", "model_provider",
        "delegator", "delegation_chain", "objective", "tool", "operation",
        "target_resource", "arguments", "credential_scope", "current_state_hash",
        "state_freshness", "reversibility", "rollback_plan?", "linked_ticket?",
        "policy_version", "correlation_id", "sequence_id",
    ],
    "included_by_digest": {
        "expected_effects": "expected_effects_digest = digest(SIMULATION, canonical(expected_effects))"
    },
    "excluded": {
        "action_id": "per-attempt id, not action identity (approval stability)",
        "timestamp": "submission time; replay handled by nonce+state, not action identity",
        "agent_identity.sig": "signature is over the payload; including it is circular",
        "approvals": "approvals bind TO action_hash; including them is circular",
        "attestation": "independently-bound evidence; rotates apart from action identity",
    },
}


def project_action_payload(envelope: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> dict:
    ai = envelope["agent_identity"]
    payload: dict[str, Any] = {
        "agent_identity": {"id": ai["id"], "key_id": ai["key_id"]},
        "runtime": envelope["runtime"],
        "model_provider": envelope["model_provider"],
        "delegator": envelope["delegator"],
        "delegation_chain": envelope["delegation_chain"],
        "objective": envelope["objective"],
        "tool": envelope["tool"],
        "operation": envelope["operation"],
        "target_resource": envelope["target_resource"],
        "arguments": envelope["arguments"],
        "credential_scope": envelope["credential_scope"],
        "current_state_hash": envelope["current_state_hash"],
        "state_freshness": envelope["state_freshness"],
        "reversibility": envelope["reversibility"],
        "policy_version": envelope["policy_version"],
        "correlation_id": envelope["correlation_id"],
        "sequence_id": envelope["sequence_id"],
    }
    if envelope.get("rollback_plan") is not None:
        payload["rollback_plan"] = envelope["rollback_plan"]
    if envelope.get("linked_ticket") is not None:
        payload["linked_ticket"] = envelope["linked_ticket"]
    if envelope.get("expected_effects") is not None:
        eff_bytes = jcs.canonicalize(envelope["expected_effects"])
        payload["expected_effects_digest"] = hashing.domain_digest(
            "SIMULATION", eff_bytes, algorithm_id=algorithm_id
        )
    return payload


def action_canonical_bytes(envelope: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> bytes:
    payload = project_action_payload(envelope, algorithm_id=algorithm_id)
    return jcs.canonicalize(payload, ENVELOPE_SET_PATHS)


def action_hash(envelope: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> str:
    payload = project_action_payload(envelope, algorithm_id=algorithm_id)
    canon = jcs.canonicalize(payload, ENVELOPE_SET_PATHS)
    return hashing.domain_digest("ACTION", canon, algorithm_id=algorithm_id)
