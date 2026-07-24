"""Real ActionGate adapter (Phase 5/7). Wraps action_gate_ref.gate.evaluate — TIER 3, pure,
deterministic, no network, NO real action execution (decision-only). Valid envelopes/policies
are built read-only via the reference package's own test helpers (env_for/signed_policy/
approval_for/ev_*). Maps the six frozen outcomes to the canonical action vocabulary; preserves
outcome, constraints, and provenance hashes. Never routes through k8s/isolated/MCP paths.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

_AGR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "cyber_security", "action_gate_reference")
if _AGR not in sys.path:
    sys.path.insert(0, _AGR)

from action_gate_ref import gate as ag_gate          # noqa: E402
from tests import helpers as agh                       # noqa: E402  (reference test builders, read-only)

from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter   # noqa: E402
from control_plane_shadow.vocabulary import ActionDisposition, map_action, provenance  # noqa: E402


class ActionGateAdapter(ShadowAdapter):
    component = "ActionGate"
    source_version = "action_gate_ref_v1"

    # canonical operations the reference gate understands (from helpers._OP_DEFAULTS)
    OPS = ("DEPLOY", "DB_DELETE", "SECRET_READ", "KEY_ROTATE", "NET_EXPOSE",
           "EXTERNAL_COMMS", "CLOUD_SPEND_INCREASE", "IAM_GRANT_ADMIN", "MONITORING_DISABLE",
           "DB_MUTATION")

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=True, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["action_disposition", "constraints", "approver_policy",
                                           "hard_safety_block", "action_hash_provenance"])

    def authorize(self, operation: str, *, with_approval: bool = False,
                  with_evidence: bool = False, now: Optional[str] = None) -> Any:
        now = now or agh.NOW
        if operation not in self.OPS:
            res = self._result(tier="TIER3", canonical={"action_disposition":
                               ActionDisposition.INDETERMINATE.value, "state": "UNKNOWN_OP"},
                               reason_codes=["ACTION.ACTION_PROPOSAL_INVALID"], health="DEGRADED",
                               error=f"unknown operation {operation!r}")
            return res
        sp = agh.signed_policy()
        env = agh.with_attestation(agh.env_for(operation)) if with_evidence else agh.env_for(operation)
        approvals = evidence = None
        if with_approval:
            approvals = [agh.approval_for(env, sp, approver_policy="dual_control", approvers=agh._DUAL)]
        if with_evidence:
            evidence = [agh.ev_backup(env), agh.ev_signed_artifact(env)]
        decision = ag_gate.evaluate(env, sp, evidence=evidence, approvals=approvals, now=now)  # REAL
        outcome = decision["outcome"]
        disp = map_action(outcome)
        hard_block = (disp == ActionDisposition.DENY and decision.get("terminal") == "DENIED"
                      and env.get("reversibility") == "IRREVERSIBLE")
        reason_map = {"ALLOW": [], "CONSTRAIN": ["ACTION.ACTION_CONSTRAINED"],
                      "APPROVE": ["ACTION.ACTION_APPROVAL_REQUIRED"],
                      "INDETERMINATE": ["ACTION.ACTION_INDETERMINATE"],
                      "DENY": ["ACTION.ACTION_DENIED"]}
        canonical = {
            "action_disposition": disp.value, "source_outcome": outcome,
            "authorized_action": operation if disp == ActionDisposition.ALLOW else None,
            "constraints": decision.get("applied_constraints"),
            "dispositive_rules": decision.get("dispositive_rules"),
            "action_hash": decision.get("action_hash"), "policy_hash": decision.get("policy_hash"),
            "terminal": decision.get("terminal"), "hard_safety_block": hard_block,
            "state": disp.value,
        }
        loss = ["state_trace and full reason text summarized to reason codes (kept in source_output)"]
        return self._result(tier="TIER3", canonical=canonical, source_output=decision,
                            reason_codes=reason_map[disp.value], information_loss=loss,
                            derived_fields=["hard_safety_block (derived from terminal+reversibility)"],
                            provenance=[provenance("ActionGate", outcome, disp)])
