"""Canonical approval object + binding validation (spec §11).

Approval binds action_hash + policy_hash (never action_id / ticket title).
Validates: action modification, policy mismatch, expiration, nonce replay,
changed constraints, scope subsumption, SoD, and approver-policy N.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from . import canon_profile as cp
from . import hashing, jcs, signing
from . import projection
from .errors import (
    ActionHashMismatchError,
    ConstraintsChangedError,
    ExpiredError,
    InvalidSignatureError,
    NonceReplayError,
    PolicyMismatchError,
    ScopeViolationError,
)

_APPROVER_MIN = {"single": 1, "budget_owner": 1, "comms_owner": 1, "dual_control": 2}


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def approval_payload_hash(payload: dict, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID) -> str:
    return hashing.domain_digest("APPROVAL", jcs.canonicalize(payload), algorithm_id=algorithm_id)


def build_approval(
    *, action_hash: str, policy_hash: str, approver_policy: str, approvers: list[dict],
    approval_scope: dict, constraints: dict, issued_at: str, expiration: str, nonce: str,
    approval_version: str = "1", decision: str = "APPROVE",
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> dict:
    payload = {
        "action_hash": action_hash,
        "policy_hash": policy_hash,
        "approver_policy": approver_policy,
        "approvers": [a["id"] for a in approvers],
        "decision": decision,
        "constraints": constraints,
        "approval_scope": approval_scope,
        "issued_at": issued_at,
        "expiration": expiration,
        "nonce": nonce,
        "approval_version": approval_version,
    }
    ah = approval_payload_hash(payload, algorithm_id=algorithm_id)
    signatures = [{"approver_id": a["id"], "key_id": a["key_id"], "sig": signing.sign(a["key_id"], ah)}
                  for a in approvers]
    return {"payload": payload, "approval_hash": ah, "hash_algorithm_id": algorithm_id,
            "signatures": signatures}


def _scope_subsumes(scope: dict, envelope: dict) -> bool:
    if scope.get("operation") != envelope["operation"]:
        return False
    scope_targets = set(scope.get("target", []))
    if not set(envelope["target_resource"]).issubset(scope_targets):
        return False
    # argument-bound subsumption: any bound key must not be exceeded (equality/subset ref check)
    for k, bound in scope.get("arg_bounds", {}).items():
        val = envelope.get("arguments", {}).get(k)
        if isinstance(bound, list):
            if val not in bound:
                return False
        elif val != bound:
            return False
    return True


def verify_approval(
    approval: dict, envelope: dict, *, active_policy_hash: str, now: str,
    used_nonces: Iterable[str] = (), expected_constraints: dict | None = None,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> bool:
    """Return True if the approval validly authorizes this envelope, else raise."""
    p = approval["payload"]

    # 1. action modification
    ah = projection.action_hash(envelope, algorithm_id=algorithm_id)
    if ah != p["action_hash"]:
        raise ActionHashMismatchError("approval does not bind this action")

    # 2. policy mismatch
    if p["policy_hash"] != active_policy_hash:
        raise PolicyMismatchError("approval bound to a different policy_hash")

    # 3. expiration
    if _parse_ts(now) >= _parse_ts(p["expiration"]):
        raise ExpiredError("approval expired")

    # 4. nonce replay
    if p["nonce"] in set(used_nonces):
        raise NonceReplayError("approval nonce already used")

    # 5. changed constraints
    if expected_constraints is not None and p["constraints"] != expected_constraints:
        raise ConstraintsChangedError("approval constraints differ from applied constraints")

    # 6. scope subsumption
    if not _scope_subsumes(p["approval_scope"], envelope):
        raise ScopeViolationError("action not subsumed by approval scope")

    # 7. signatures valid, independent, SoD-satisfying, approver-policy N
    recomputed = approval_payload_hash(p, algorithm_id=algorithm_id)
    if recomputed != approval["approval_hash"]:
        raise InvalidSignatureError("approval_hash mismatch")
    delegator_id = envelope["delegator"]["id"]
    agent_principal = envelope["credential_scope"]["principal"]
    valid_ids = set()
    for s in approval["signatures"]:
        if not signing.verify(s["key_id"], approval["approval_hash"], s["sig"]):
            raise InvalidSignatureError(f"bad signature from {s['approver_id']}")
        if s["approver_id"] in (delegator_id, agent_principal):
            raise ScopeViolationError("SoD violation: approver == requester/agent")
        valid_ids.add(s["approver_id"])
    need = _APPROVER_MIN.get(p["approver_policy"], 1)
    if len(valid_ids) < need:
        raise ScopeViolationError(
            f"approver_policy {p['approver_policy']} needs {need}, got {len(valid_ids)}")
    return True
