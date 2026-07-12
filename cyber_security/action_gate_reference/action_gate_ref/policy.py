"""Signed policy bundle + policy_hash + the default ruleset.

The ruleset encodes the ten example hard-invariant rules (ACTION_GATE_SPECIFICATION.md
§4) in a compact, deterministic schema the gate evaluator (gate.py) consumes.
Policy is signed by an out-of-band root of trust (reference key 'root_of_trust').
"""

from __future__ import annotations

from typing import Any

from . import canon_profile as cp
from . import hashing, jcs, signing

# Effect ops (gate spec §4). Each effect may carry a `when_fact` guard.
DEFAULT_RULES = [
    {"id": "R1", "operation": "IAM_GRANT_ADMIN", "effects": [
        {"op": "DENY", "when_fact": "self_grant"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "dual_control"},
        {"op": "REQUIRE_ATTESTATION", "attn_type": "workload-identity"},
        {"op": "ALLOW"},
    ]},
    {"id": "R2", "operation": "DEPLOY", "effects": [
        {"op": "MUST_HAVE", "evidence": "signed_artifact"},
        {"op": "REQUIRE_SIMULATION", "fidelity": "HIGH"},
        {"op": "ALLOW"},
    ]},
    {"id": "R3", "operation": "DB_DELETE", "effects": [
        {"op": "FORBID", "fact": "last_replica"},
        # `hard`: for this irreversible destructive class a missing verified backup
        # is dispositive DENY, not REQUEST_MORE_EVIDENCE (IMPLEMENTATION_FINDINGS #1).
        {"op": "MUST_HAVE", "evidence": "verified_restorable_backup", "hard": True},
        {"op": "MAX_IRREVERSIBILITY", "class": "REVERSIBLE_WITH_COST"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "dual_control"},
        {"op": "ALLOW"},
    ]},
    {"id": "R4", "operation": "NET_EXPOSE", "effects": [
        {"op": "DENY", "when_fact": "public_sensitive"},
        {"op": "DENY", "when_fact": "admin_port_public"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "single", "when_fact": "widening"},
        {"op": "ALLOW"},
    ]},
    {"id": "R5", "operation": "SECRET_READ", "effects": [
        {"op": "FORBID", "fact": "export_unapproved"},
        {"op": "FORBID", "fact": "bulk"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "single"},
        {"op": "ALLOW_WITH_CONSTRAINTS", "constraints": {"post_read_rotation": True}},
    ]},
    {"id": "R6", "operation": "MONITORING_DISABLE", "effects": [
        {"op": "FORBID", "fact": "gate_audit_target"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "dual_control"},
        {"op": "ALLOW_WITH_CONSTRAINTS", "constraints": {"auto_reenable": True}},
    ]},
    {"id": "R7", "operation": "DB_MUTATION", "effects": [
        {"op": "FORBID", "fact": "unbounded"},
        {"op": "REQUIRE_SIMULATION", "fidelity": "MEDIUM"},
        {"op": "MAX_SCOPE", "value": "10000", "fact": "affected_count"},
        {"op": "ALLOW_WITH_CONSTRAINTS", "constraints": {"in_transaction": True}},
    ]},
    {"id": "R8", "operation": "KEY_ROTATE", "effects": [
        {"op": "FORBID", "fact": "trust_root_outside_process"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "single", "when_fact": "live_dependents"},
        {"op": "ALLOW"},
    ]},
    {"id": "R9", "operation": "CLOUD_SPEND_INCREASE", "effects": [
        {"op": "FORBID", "fact": "self_approved"},
        {"op": "MAX_COST", "value": "100000", "fact": "projected_cost"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "budget_owner", "when_fact": "large_delta"},
        {"op": "ALLOW"},
    ]},
    {"id": "R10", "operation": "EXTERNAL_COMMS", "effects": [
        {"op": "DENY", "when_fact": "free_text"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "comms_owner"},
        {"op": "ALLOW_WITH_CONSTRAINTS", "constraints": {"approved_template": True}},
    ]},
]

# per-class evidence freshness bound (seconds) — spec-declared policy values
FRESHNESS_BOUND_SECONDS = 600


def build_bundle(rules: list | None = None, *, effective_time: str = "2026-01-01T00:00:00.000Z",
                 version: str = "1.4.0") -> dict:
    return {
        "rules": rules if rules is not None else DEFAULT_RULES,
        "metadata": {"name": "reference-prod-infra", "version": version},
        "effective_time": effective_time,
        "parent_ref": None,
        "root_ref": "policy://root/v1",
        "freshness_bound_seconds": str(FRESHNESS_BOUND_SECONDS),
        "canonicalization_version": cp.CANONICALIZATION_VERSION,
        "policy_schema_version": cp.POLICY_SCHEMA_VERSION,
    }


def policy_hash(bundle: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> str:
    canon = jcs.canonicalize(bundle)
    return hashing.domain_digest("POLICY", canon, algorithm_id=algorithm_id)


def policy_version(bundle: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> str:
    return f"{bundle['metadata']['version']}+{algorithm_id.replace('-', '')}:{policy_hash(bundle, algorithm_id=algorithm_id)}"


def sign_policy(bundle: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> dict:
    ph = policy_hash(bundle, algorithm_id=algorithm_id)
    return {
        "bundle": bundle,
        "policy_hash": ph,
        "hash_algorithm_id": algorithm_id,
        "root_of_trust_key": "root_of_trust",
        "signature": signing.sign("root_of_trust", ph),
    }


def verify_policy(signed: dict) -> bool:
    ph = policy_hash(signed["bundle"], algorithm_id=signed["hash_algorithm_id"])
    if ph != signed["policy_hash"]:
        return False
    return signing.verify(signed["root_of_trust_key"], ph, signed["signature"])
