"""Phase 5 - Native ActionGate vocabulary contract (MANDATORY).

The customer-shadow-readiness adapter compressed the real gate's SIX native outcomes into a FOUR-value
shadow vocabulary - a tracked 25% semantic loss (ALLOW_WITH_CONSTRAINTS, REQUEST_MORE_EVIDENCE, and
SIMULATE_AND_RETRY were all flattened). This module is the pilot's answer to the mandate: a NATIVE
contract that invokes the real frozen gate read-only and preserves EVERY native outcome and its
metadata with ZERO loss.

Preserved exactly (no collapse):
  outcomes            ALLOW · ALLOW_WITH_CONSTRAINTS · DENY · ESCALATE_TO_HUMAN ·
                      REQUEST_MORE_EVIDENCE · SIMULATE_AND_RETRY
  metadata            constraints, approvals (required/satisfied), evidence requirements,
                      simulation, retry, reason codes / dispositive rules, policy references,
                      action hash, policy hash, state trace, terminal, hash algorithm id

Pilot blocker: any semantic loss in a SAFETY-RELEVANT native outcome. This module's contract makes
loss = 0 by construction and provides `semantic_loss_report()` to prove it and to fail the pilot if a
future change ever reintroduces loss.

Read-only: wraps `cyber_security/action_gate_reference/action_gate_ref/gate.py`; re-implements no
decision logic. Non-enforcing: the gate only DECIDES; the pilot never executes. Deterministic (fixed
reference clock).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_AGR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "cyber_security", "action_gate_reference")
if _AGR not in sys.path:
    sys.path.insert(0, _AGR)

from action_gate_ref import gate as _real_gate          # noqa: E402  (read-only)
from tests import helpers as _h                          # noqa: E402  (reference read-only builders)

SOURCE_VERSION = "action_gate_ref_v1"
CONTRACT_VERSION = "native_actiongate_contract_v1"
NOW = _h.NOW

# The complete native vocabulary - preserved verbatim, never collapsed.
NATIVE_OUTCOMES = (
    "ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
    "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY",
)

# Safety-relevant native outcomes: losing or downgrading any of these is a PILOT BLOCKER. (Every
# non-ALLOW outcome carries a restraint; ALLOW_WITH_CONSTRAINTS carries binding constraints.)
SAFETY_RELEVANT = frozenset({
    "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
    "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY",
})

# Permissiveness order (higher = more permissive). Used only to detect an unsafe DOWNGRADE, never to
# collapse outcomes. Mirrors the gate's own severity ordering.
_PERMISSIVENESS = {
    "DENY": 0, "REQUEST_MORE_EVIDENCE": 1, "SIMULATE_AND_RETRY": 2,
    "ESCALATE_TO_HUMAN": 3, "ALLOW_WITH_CONSTRAINTS": 4, "ALLOW": 5,
}

# Semantic role of each native outcome, preserved as structured flags (NOT a lossy remap - every
# outcome keeps its own identity in `native_outcome`).
_SEMANTICS = {
    "ALLOW":                  {"permits": True},
    "ALLOW_WITH_CONSTRAINTS": {"permits": True, "requires_constraints": True},
    "DENY":                   {"blocks": True},
    "ESCALATE_TO_HUMAN":      {"requires_human": True},
    "REQUEST_MORE_EVIDENCE":  {"requires_evidence": True},
    "SIMULATE_AND_RETRY":     {"requires_simulation": True, "requires_retry": True},
}


@dataclass
class NativeActionDecision:
    native_outcome: str                          # the real gate outcome, VERBATIM (never collapsed)
    is_native: bool                              # True unless a gate error produced a non-outcome
    semantics: Dict[str, bool] = field(default_factory=dict)
    requires_constraints: bool = False
    requires_human: bool = False
    requires_evidence: bool = False
    requires_simulation: bool = False
    requires_retry: bool = False
    permits: bool = False
    blocks: bool = False
    applied_constraints: Any = None              # constraints, preserved
    dispositive_rules: List[str] = field(default_factory=list)   # reason codes / policy references
    approvals_required: bool = False
    approvals_satisfied: bool = False
    action_hash: str = ""
    policy_hash: str = ""
    hash_algorithm_id: str = ""
    state_trace: List[str] = field(default_factory=list)
    terminal: str = ""
    reason: str = ""
    fail_closed: bool = False
    error: str = ""
    source_version: str = SOURCE_VERSION
    contract_version: str = CONTRACT_VERSION


# ---- input construction (reuses the reference's own read-only builders) --------------------------
OP_MAP = {
    "transfer_funds": "CLOUD_SPEND_INCREASE", "delete_records": "DB_DELETE", "deploy": "DEPLOY",
    "disable": "MONITORING_DISABLE", "enable": "NET_EXPOSE", "grant": "IAM_GRANT_ADMIN",
    "revoke": "IAM_GRANT_ADMIN", "send": "EXTERNAL_COMMS", "purchase": "CLOUD_SPEND_INCREASE",
    "terminate": "DB_DELETE", "refund": "CLOUD_SPEND_INCREASE", "escalate": "EXTERNAL_COMMS",
    "restart": "DEPLOY", "shut down": "MONITORING_DISABLE", "secret_read": "SECRET_READ",
    "key_rotate": "KEY_ROTATE", "db_mutation": "DB_MUTATION",
}


def _operation_for(action: Dict[str, Any]) -> str:
    return OP_MAP.get((action or {}).get("action_type", ""), "EXTERNAL_COMMS")


def _build_inputs(action: Dict[str, Any], operation: str):
    env = _h.with_attestation(_h.env_for(operation))
    sp = _h.signed_policy()
    evidence = [_h.ev_backup(env), _h.ev_signed_artifact(env)]
    granted = bool(action.get("authority_granted"))
    approvals = [_h.approval_for(env, sp, approver_policy="dual_control", approvers=_h._DUAL)] if granted \
        else []
    return env, sp, evidence, approvals


def _from_decision(d: Dict[str, Any], approvals_required: bool, approvals_satisfied: bool) -> NativeActionDecision:
    outcome = d.get("outcome", "")
    sem = dict(_SEMANTICS.get(outcome, {}))
    return NativeActionDecision(
        native_outcome=outcome,
        is_native=outcome in NATIVE_OUTCOMES,
        semantics=sem,
        requires_constraints=sem.get("requires_constraints", False),
        requires_human=sem.get("requires_human", False),
        requires_evidence=sem.get("requires_evidence", False),
        requires_simulation=sem.get("requires_simulation", False),
        requires_retry=sem.get("requires_retry", False),
        permits=sem.get("permits", False),
        blocks=sem.get("blocks", False),
        applied_constraints=d.get("applied_constraints"),
        dispositive_rules=list(d.get("dispositive_rules") or []),
        approvals_required=approvals_required,
        approvals_satisfied=approvals_satisfied,
        action_hash=d.get("action_hash", ""),
        policy_hash=d.get("policy_hash", ""),
        hash_algorithm_id=d.get("hash_algorithm_id", ""),
        state_trace=list(d.get("state_trace") or []),
        terminal=d.get("terminal", ""),
        reason=d.get("reason", ""),
    )


def evaluate(action: Optional[Dict[str, Any]]) -> Optional[NativeActionDecision]:
    """Evaluate a pilot action proposal through the real gate, preserving the native outcome. Returns
    None when there is no action to gate (advisory-only artifact). Fails closed on any gate error to a
    non-native, maximally restrictive decision that is NEVER permissive."""
    if action is None:
        return None
    operation = _operation_for(action)
    try:
        env, sp, evidence, approvals = _build_inputs(action, operation)
        d = _real_gate.evaluate(env, sp, evidence=evidence, approvals=approvals, now=NOW)
    except Exception as e:  # GateError / malformed -> fail closed, non-native, restrictive
        return NativeActionDecision(
            native_outcome="GATE_ERROR", is_native=False, blocks=True, fail_closed=True,
            terminal="FAILED_CLOSED", error=f"{type(e).__name__}: {e}",
            dispositive_rules=["GATE_ERROR_FAIL_CLOSED"])
    return _from_decision(d, approvals_required=True, approvals_satisfied=bool(approvals))


def evaluate_raw_operation(operation: str, *, evidence=None, approvals=None, env_over=None,
                           mutate=None) -> NativeActionDecision:
    """Drive the real gate for a specific canonical operation with explicit scaffolding. Used by the
    Phase-5 conformance fixtures to exercise every one of the six native outcomes. Read-only."""
    try:
        base = _h.env_for(operation, **(env_over or {}))
        if mutate:
            base = mutate(base)
        d = _real_gate.evaluate(base, _h.signed_policy(), evidence=evidence, approvals=approvals, now=NOW)
    except Exception as e:
        return NativeActionDecision(native_outcome="GATE_ERROR", is_native=False, blocks=True,
                                    fail_closed=True, error=f"{type(e).__name__}: {e}")
    return _from_decision(d, approvals_required=bool(approvals), approvals_satisfied=bool(approvals))


# ---- conformance: prove all six native outcomes survive with zero loss --------------------------
def _fixtures() -> Dict[str, NativeActionDecision]:
    """Deterministic scaffolding (from the reference's own acceptance suite) that drives the real gate
    to each of the six native outcomes. Returns {expected_outcome: decision}."""
    DUAL = _h._DUAL
    sp = _h.signed_policy()
    out: Dict[str, NativeActionDecision] = {}

    def _run(env, evidence, approvals):
        d = _real_gate.evaluate(env, sp, evidence=evidence, approvals=approvals, now=NOW)
        return _from_decision(d, approvals_required=bool(approvals), approvals_satisfied=bool(approvals))

    # ALLOW - satisfied happy path for a low-consequence op
    e, ev, ap, _ = _h.happy("DEPLOY")
    out["ALLOW"] = _run(e, ev, ap)

    # ALLOW_WITH_CONSTRAINTS - happy path for a constrained-allow op (carries applied_constraints)
    e, ev, ap, _ = _h.happy("SECRET_READ")
    out["ALLOW_WITH_CONSTRAINTS"] = _run(e, ev, ap)

    # DENY - irreversible destructive op missing a hard MUST_HAVE precondition (backup)
    e = _h.env_for("DB_DELETE", reversibility="REVERSIBLE_WITH_COST")
    ap = [_h.approval_for(e, sp, approver_policy="dual_control", approvers=DUAL)]
    out["DENY"] = _run(e, None, ap)

    # ESCALATE_TO_HUMAN - high-consequence op fully evidenced+approved still requires a human
    e = _h.with_attestation(_h.env_for("DB_DELETE"))
    ap = [_h.approval_for(e, sp, approver_policy="dual_control", approvers=DUAL)]
    out["ESCALATE_TO_HUMAN"] = _run(e, [_h.ev_backup(e), _h.ev_signed_artifact(e)], ap)

    # REQUEST_MORE_EVIDENCE - IAM grant with dual approval but no attestation
    e = _h.env_for("IAM_GRANT_ADMIN")
    ap = [_h.approval_for(e, sp, approver_policy="dual_control", approvers=DUAL)]
    out["REQUEST_MORE_EVIDENCE"] = _run(e, None, ap)

    # SIMULATE_AND_RETRY - DEPLOY with artifact present but simulation absent
    e = _h.env_for("DEPLOY")
    out["SIMULATE_AND_RETRY"] = _run(e, [_h.ev_signed_artifact(e)], None)

    return out


def conformance() -> Dict[str, Any]:
    """Verify the native contract reproduces every one of the six native outcomes and preserves their
    metadata. Returns a structured report; `all_native_outcomes_preserved` must be True."""
    fx = _fixtures()
    rows = []
    preserved = 0
    for expected in NATIVE_OUTCOMES:
        d = fx.get(expected)
        ok = d is not None and d.native_outcome == expected and d.is_native
        if ok:
            preserved += 1
        rows.append({
            "expected": expected,
            "native_outcome": d.native_outcome if d else None,
            "preserved": ok,
            "has_action_hash": bool(d and d.action_hash),
            "has_policy_hash": bool(d and d.policy_hash),
            "has_state_trace": bool(d and d.state_trace),
            "dispositive_rules": d.dispositive_rules if d else [],
            "applied_constraints_present": bool(d and d.applied_constraints),
            "semantics": d.semantics if d else {},
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "native_outcomes": list(NATIVE_OUTCOMES),
        "outcomes_preserved": preserved,
        "outcomes_total": len(NATIVE_OUTCOMES),
        "all_native_outcomes_preserved": preserved == len(NATIVE_OUTCOMES),
        "rows": rows,
    }


def semantic_loss_report() -> Dict[str, Any]:
    """The pilot-blocker gate. The native contract must preserve every safety-relevant outcome with
    zero loss. Compares against the customer-shadow-readiness lossy shadow mapping to quantify what the
    native contract recovers. `blocker` is True iff any safety-relevant native outcome is lost."""
    from customer_shadow_readiness.adapters.real_action_gate import OUTCOME_TO_SHADOW, _LOSSY_OUTCOMES

    # Shadow mapping collapses 6 -> 4 distinct values; the native contract keeps all 6.
    shadow_distinct = len(set(OUTCOME_TO_SHADOW.values()))
    native_distinct = len(NATIVE_OUTCOMES)
    lost_under_shadow = sorted(_LOSSY_OUTCOMES.keys())

    conf = conformance()
    # A safety-relevant outcome is "lost" if the native contract fails to preserve it verbatim.
    lost_native = [r["expected"] for r in conf["rows"]
                   if r["expected"] in SAFETY_RELEVANT and not r["preserved"]]

    return {
        "contract_version": CONTRACT_VERSION,
        "native_distinct_outcomes": native_distinct,
        "shadow_distinct_outcomes": shadow_distinct,
        # structural facts, precisely labelled (not the prior study's case-level 25% figure):
        "outcomes_collapsed_under_shadow_mapping": len(lost_under_shadow),   # 3 of 6
        "shadow_distinct_vocab_reduction_pct": round(
            100 * (native_distinct - shadow_distinct) / native_distinct, 1),
        "native_semantic_loss_pct": 0.0 if not lost_native else round(
            100 * len(lost_native) / native_distinct, 1),
        "outcomes_lost_under_shadow_mapping": lost_under_shadow,
        "safety_relevant_outcomes_lost_under_native_contract": lost_native,
        "recovered_by_native_contract": lost_under_shadow if not lost_native else [],
        "blocker": bool(lost_native),          # pilot blocker iff any safety-relevant outcome lost
    }


if __name__ == "__main__":
    c = conformance()
    print(f"conformance: {c['outcomes_preserved']}/{c['outcomes_total']} native outcomes preserved "
          f"-> all_preserved={c['all_native_outcomes_preserved']}")
    for r in c["rows"]:
        print(f"  {r['expected']:24s} native={r['native_outcome']:24s} preserved={r['preserved']} "
              f"rules={r['dispositive_rules']}")
    s = semantic_loss_report()
    print(f"outcomes collapsed under shadow mapping: {s['outcomes_collapsed_under_shadow_mapping']}/6  "
          f"native loss: {s['native_semantic_loss_pct']}%")
    print(f"recovered by native contract: {s['recovered_by_native_contract']}")
    print(f"PILOT BLOCKER: {s['blocker']}")
