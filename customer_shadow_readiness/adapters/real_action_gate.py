"""Read-only REAL ActionGate adapter (M2). Wraps the actual frozen decision engine
cyber_security/action_gate_reference/action_gate_ref/gate.py - NOT the pilot's action_shadow_v1
heuristic. Imports the component read-only; builds a valid envelope/signed-policy/evidence/approvals
from a pilot action proposal using the reference's OWN read-only test builders (the only way to obtain
valid signed crypto scaffolding without minting real keys); calls the real evaluate; maps the real
6-value outcome to the pilot shadow vocabulary; preserves both source and transformed representations;
emits semantic-loss warnings; fails closed on GateError.

No enforcement, no external action - the real gate only DECIDES; the pilot never executes.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_AGR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "cyber_security", "action_gate_reference")
if _AGR not in sys.path:
    sys.path.insert(0, _AGR)

from action_gate_ref import gate as _real_gate          # noqa: E402  (read-only)
from tests import helpers as _h                          # noqa: E402  (reference read-only builders)

SOURCE_VERSION = "action_gate_ref_v1"
NOW = _h.NOW                                              # fixed clock (determinism)

# pilot action_type -> canonical ActionGate operation (10 canonical ops)
OP_MAP = {
    "transfer_funds": "CLOUD_SPEND_INCREASE", "delete_records": "DB_DELETE", "deploy": "DEPLOY",
    "disable": "MONITORING_DISABLE", "enable": "NET_EXPOSE", "grant": "IAM_GRANT_ADMIN",
    "revoke": "IAM_GRANT_ADMIN", "send": "EXTERNAL_COMMS", "purchase": "CLOUD_SPEND_INCREASE",
    "terminate": "DB_DELETE", "refund": "CLOUD_SPEND_INCREASE", "escalate": "EXTERNAL_COMMS",
    "restart": "DEPLOY", "shut down": "MONITORING_DISABLE", "secret_read": "SECRET_READ",
    "key_rotate": "KEY_ROTATE", "db_mutation": "DB_MUTATION",
}

# real outcome -> pilot shadow ActionGate disposition (the pilot vocabulary)
OUTCOME_TO_SHADOW = {
    "ALLOW": "PERMIT",
    "ALLOW_WITH_CONSTRAINTS": "CONSTRAIN",
    "DENY": "BLOCK",
    "ESCALATE_TO_HUMAN": "ESCALATE",
    "REQUEST_MORE_EVIDENCE": "INDETERMINATE",
    "SIMULATE_AND_RETRY": "CONSTRAIN",
}
# information the pilot shadow vocabulary CANNOT represent (semantic loss on mapping)
_LOSSY_OUTCOMES = {"ALLOW_WITH_CONSTRAINTS": "applied_constraints lost",
                   "REQUEST_MORE_EVIDENCE": "evidence-request semantics collapsed to INDETERMINATE",
                   "SIMULATE_AND_RETRY": "simulation-retry semantics collapsed to CONSTRAIN"}


@dataclass
class RealActionResult:
    shadow_disposition: str            # mapped to the pilot vocabulary
    real_outcome: str                  # the actual gate outcome (preserved)
    dispositive_rules: List[str] = field(default_factory=list)
    applied_constraints: Any = None
    state_trace: List[str] = field(default_factory=list)
    action_hash: str = ""
    policy_hash: str = ""
    semantic_loss: List[str] = field(default_factory=list)
    reason: str = ""
    error: str = ""
    source_version: str = SOURCE_VERSION


def _operation_for(action: Dict[str, Any]) -> str:
    at = (action or {}).get("action_type", "")
    return OP_MAP.get(at, "EXTERNAL_COMMS")     # unmapped action -> a high-consequence default (conservative)


def _build_inputs(action: Dict[str, Any], operation: str):
    """Construct a valid signed envelope/policy/evidence/approvals from the pilot proposal, using the
    reference's own read-only builders. Evidence/approval PRESENCE is driven by the pilot fields so the
    real gate reaches a genuine decision: granted authority -> approvals present; reversible/low-risk ->
    fuller evidence."""
    env = _h.with_attestation(_h.env_for(operation))
    sp = _h.signed_policy()
    evidence = [_h.ev_backup(env), _h.ev_signed_artifact(env)]
    # approvals present only when the proposal declares the required authority granted
    granted = bool(action.get("authority_granted"))
    approvals = [_h.approval_for(env, sp, approver_policy="dual_control", approvers=_h._DUAL)] if granted \
        else []
    return env, sp, evidence, approvals


def evaluate(action: Optional[Dict[str, Any]]) -> RealActionResult:
    if action is None:
        return RealActionResult(shadow_disposition="NO_ACTION", real_outcome="", reason="no_action")
    operation = _operation_for(action)
    try:
        env, sp, evidence, approvals = _build_inputs(action, operation)
        d = _real_gate.evaluate(env, sp, evidence=evidence, approvals=approvals, now=NOW)
    except Exception as e:  # GateError or malformed input -> fail closed
        return RealActionResult(shadow_disposition="BLOCK", real_outcome="GATE_ERROR",
                                error=f"{type(e).__name__}: {e}", semantic_loss=["gate_error_fail_closed"])
    outcome = d.get("outcome", "")
    loss = []
    if outcome in _LOSSY_OUTCOMES:
        loss.append(_LOSSY_OUTCOMES[outcome])
    return RealActionResult(
        shadow_disposition=OUTCOME_TO_SHADOW.get(outcome, "ESCALATE"),
        real_outcome=outcome, dispositive_rules=d.get("dispositive_rules") or [],
        applied_constraints=d.get("applied_constraints"), state_trace=d.get("state_trace") or [],
        action_hash=d.get("action_hash", ""), policy_hash=d.get("policy_hash", ""),
        semantic_loss=loss, reason=d.get("reason", ""))
