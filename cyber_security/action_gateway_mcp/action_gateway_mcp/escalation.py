"""Reference human-escalation queue + exact-action approval helper.

An escalated request captures everything a human approver needs to make a bound
decision. Approvals are created through the frozen approval-binding implementation
(``action_gate_ref.approval``) and bind to the EXACT action hash + policy hash —
there is no automatic or AI approval path.
"""

from __future__ import annotations

from ._core import ref_approval

# reference approver identities (test keys in the frozen signing keyring)
APPROVERS = {
    "security-lead": {"id": "security-lead", "key_id": "approver:security-lead"},
    "sre-lead": {"id": "sre-lead", "key_id": "approver:sre-lead"},
    "budget-owner": {"id": "budget-owner", "key_id": "approver:budget-owner"},
    "comms-owner": {"id": "comms-owner", "key_id": "approver:comms-owner"},
}

_POLICY_APPROVERS = {
    "dual_control": ["security-lead", "sre-lead"],
    "single": ["security-lead"],
    "budget_owner": ["budget-owner"],
    "comms_owner": ["comms-owner"],
}


class EscalationQueue:
    def __init__(self):
        self._entries: dict[str, dict] = {}
        self._n = 0

    def push(self, *, request_id, action_hash, action_summary, dispositive_rules,
             approval_scope, consequence, required_approver_roles, expiry,
             correlation_id) -> str:
        self._n += 1
        eid = f"esc-{self._n}"
        self._entries[eid] = {
            "escalation_id": eid, "request_id": request_id, "action_hash": action_hash,
            "action_summary": action_summary, "dispositive_rules": dispositive_rules,
            "approval_scope": approval_scope, "consequence": consequence,
            "required_approver_roles": required_approver_roles, "expiry": expiry,
            "correlation_id": correlation_id, "status": "OPEN",
        }
        return eid

    def get(self, eid: str) -> dict | None:
        return self._entries.get(eid)

    def list(self) -> list:
        return list(self._entries.values())

    def close(self, eid: str) -> None:
        if eid in self._entries:
            self._entries[eid]["status"] = "APPROVED"

    def snapshot(self) -> dict:
        return {"entries": self._entries, "n": self._n}

    def restore(self, snap: dict) -> None:
        self._entries = dict(snap.get("entries", {}))
        self._n = snap.get("n", 0)


def build_approval(*, action_hash, policy_hash, operation, target, approver_policy,
                   issued_at, expiration, nonce, clock=None):
    """Create an exact-action, exact-policy approval via the frozen implementation."""
    approver_ids = _POLICY_APPROVERS.get(approver_policy, ["security-lead"])
    approvers = [APPROVERS[i] for i in approver_ids]
    return ref_approval.build_approval(
        action_hash=action_hash, policy_hash=policy_hash,
        approver_policy=approver_policy, approvers=approvers,
        approval_scope={"operation": operation, "target": target},
        constraints={}, issued_at=issued_at, expiration=expiration, nonce=nonce)
