"""Action-hash projection: the exact inclusion/exclusion rules (spec §10).

Included: authorization-relevant fields. Excluded (justified): action_id,
timestamp, agent_identity.sig, approvals, attestation. Included-by-digest:
expected_effects -> expected_effects_digest (SIMULATION domain).

Identity profiles
-----------------
* ``v1`` (default, frozen legacy): the historical projection. Unchanged, so all
  pre-existing conformance vectors, approvals, and evidence bindings verify
  byte-for-byte. ``runtime``, ``model_provider``, ``objective`` are INCLUDED.
* ``v2`` (CER V0.1): identical fields EXCEPT the three decision-inert provenance
  fields (``runtime``, ``model_provider``, ``objective``) are EXCLUDED from the
  action identity. They remain in the validated envelope and the decision/audit
  record — only the *identity* changes. This lets the same actuation produced by
  different runtimes (which differ only in provenance) hash to the same
  ``action_hash``. Justification per field is in ``V2_EXCLUDED`` below; each was
  verified decision-inert (no predicate in gate.py reads it) and not used for
  approval/evidence binding except *through* action_hash itself.

The two profiles are domain-separated by ``envelope_schema_version`` in the hash
frame (v1="1.0.0", v2="2.0.0"), so a v1 and a v2 action_hash of the same envelope
are always different values and cannot be confused.
"""

from __future__ import annotations

from typing import Any

from . import canon_profile as cp
from . import hashing, jcs
from .schema import ENVELOPE_SET_PATHS

# Provenance fields removed from identity under profile v2. Each is decision-inert
# (grep of gate.py: no predicate reads them) and only present for traceability.
V2_EXCLUDED = {
    "runtime": "runtime/framework label; no decision predicate reads it (provenance only)",
    "model_provider": "producing model+provider; decision-inert (provenance only)",
    "objective": "task/purpose prose; spec Tier-3 advisory, never in the reference decision path",
}

# machine-readable projection manifest (spec §10)
PROJECTION_MANIFEST = {
    "canonicalization_version": cp.CANONICALIZATION_VERSION,
    "envelope_schema_version": cp.ENVELOPE_SCHEMA_VERSION,
    "identity_profile": "v1",
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

# v2 manifest: same as v1 but the three provenance fields move from included -> excluded.
PROJECTION_MANIFEST_V2 = {
    **PROJECTION_MANIFEST,
    "envelope_schema_version": cp.ENVELOPE_SCHEMA_VERSION_V2,
    "identity_profile": "v2",
    "included": [f for f in PROJECTION_MANIFEST["included"]
                 if f not in ("runtime", "model_provider", "objective")],
    "excluded": {**PROJECTION_MANIFEST["excluded"], **V2_EXCLUDED},
}


def _schema_version_for(identity_profile: str) -> str:
    if identity_profile == "v1":
        return cp.ENVELOPE_SCHEMA_VERSION
    if identity_profile == "v2":
        return cp.ENVELOPE_SCHEMA_VERSION_V2
    raise ValueError(f"unknown identity_profile {identity_profile!r}")


def project_action_payload(
    envelope: dict,
    *,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
    identity_profile: str = cp.DEFAULT_IDENTITY_PROFILE,
) -> dict:
    """Build the projected payload that is hashed to form the action identity.

    ``identity_profile`` selects v1 (legacy, provenance included) or v2 (CER V0.1,
    provenance excluded). v1 is byte-for-byte the historical behaviour.
    """
    if identity_profile not in cp.IDENTITY_PROFILES:
        raise ValueError(f"unknown identity_profile {identity_profile!r}")
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
    if identity_profile == "v2":
        # Remove the decision-inert provenance fields from the *identity* only.
        for k in V2_EXCLUDED:
            payload.pop(k, None)
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


def action_canonical_bytes(
    envelope: dict,
    *,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
    identity_profile: str = cp.DEFAULT_IDENTITY_PROFILE,
) -> bytes:
    payload = project_action_payload(
        envelope, algorithm_id=algorithm_id, identity_profile=identity_profile)
    return jcs.canonicalize(payload, ENVELOPE_SET_PATHS)


def action_hash(
    envelope: dict,
    *,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
    identity_profile: str = cp.DEFAULT_IDENTITY_PROFILE,
) -> str:
    payload = project_action_payload(
        envelope, algorithm_id=algorithm_id, identity_profile=identity_profile)
    canon = jcs.canonicalize(payload, ENVELOPE_SET_PATHS)
    return hashing.domain_digest(
        "ACTION", canon,
        algorithm_id=algorithm_id,
        schema_version=_schema_version_for(identity_profile),
    )
