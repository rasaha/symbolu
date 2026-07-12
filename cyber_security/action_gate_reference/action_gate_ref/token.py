"""Execution authorization token (spec §15).

Short-lived, gate-signed. The broker/tool rejects expired, replayed, modified,
scope-expanded, retargeted, action-mismatched, or policy-mismatched calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from . import canon_profile as cp
from . import hashing, jcs, projection, signing
from .errors import (
    ActionHashMismatchError,
    ExpiredError,
    NonceReplayError,
    PolicyMismatchError,
    ScopeViolationError,
    TargetMismatchError,
    StaleStateError,
)


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def build_token(
    *, action_hash: str, permitted_operation: str, permitted_target: list,
    credential_scope: dict, constraints: dict, expiration: str, nonce: str,
    policy_hash: str, decision_record_hash: str,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> dict:
    payload = {
        "action_hash": action_hash,
        "permitted_operation": permitted_operation,
        "permitted_target": permitted_target,
        "credential_scope": credential_scope,
        "constraints": constraints,
        "expiration": expiration,
        "nonce": nonce,
        "policy_hash": policy_hash,
        "decision_record_hash": decision_record_hash,
    }
    th = hashing.domain_digest("EXECUTION_TOKEN", jcs.canonicalize(payload), algorithm_id=algorithm_id)
    return {"payload": payload, "token_hash": th, "hash_algorithm_id": algorithm_id,
            "signature": signing.sign("gate", th)}


def verify_token(
    token: dict, call_envelope: dict, *, active_policy_hash: str, now: str,
    used_nonces: Iterable[str] = (), require_reeval: bool = False,
    current_state_hash: str | None = None,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> bool:
    """Return True iff the token authorizes this exact call, else raise."""
    p = token["payload"]

    if not signing.verify("gate", token["token_hash"], token["signature"]):
        raise ScopeViolationError("token signature invalid")

    # expired
    if _parse_ts(now) >= _parse_ts(p["expiration"]):
        raise ExpiredError("token expired")

    # nonce replay
    if p["nonce"] in set(used_nonces):
        raise NonceReplayError("token nonce reused")

    # action modification -> recompute action_hash from the actual call
    if projection.action_hash(call_envelope, algorithm_id=algorithm_id) != p["action_hash"]:
        raise ActionHashMismatchError("token does not bind this call's action")

    # operation / target
    if call_envelope["operation"] != p["permitted_operation"]:
        raise TargetMismatchError("operation differs from permitted_operation")
    if not set(call_envelope["target_resource"]).issubset(set(p["permitted_target"])):
        raise TargetMismatchError("call target not within permitted_target")

    # argument expansion beyond constraints
    for k, bound in p["constraints"].get("arg_bounds", {}).items():
        val = call_envelope.get("arguments", {}).get(k)
        if isinstance(bound, list):
            if val not in bound:
                raise ScopeViolationError(f"argument {k} expanded beyond token bound")
        elif val != bound:
            raise ScopeViolationError(f"argument {k} expanded beyond token bound")

    # policy mismatch where re-evaluation required
    if require_reeval and p["policy_hash"] != active_policy_hash:
        raise PolicyMismatchError("policy changed; re-evaluation required")

    # TOCTOU: commit-time state must match token's approved-against state
    if current_state_hash is not None and current_state_hash != call_envelope["current_state_hash"]:
        raise StaleStateError("current state changed since approval; re-evaluate")

    return True
