"""Translate a transport-neutral tool request into a canonical action envelope.

The frozen envelope taxonomy is infrastructure-operation-centric (ten operations
in ``ACTION_GATE_SPECIFICATION.md §2``); tool verbs must therefore be *mapped*
onto those operations. This module is the mapping layer: it owns the
(tool, verb) -> operation table, the per-verb permission strings, and the
assembly of a schema-valid 24-field envelope. It performs NO policy reasoning —
admissibility is decided only by the frozen gate.

All numeric argument values must be typed strings (Action Profile: no bare JSON
numbers); booleans are permitted. Callers supply operation facts inside
``args`` and the mapper passes them through verbatim.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# single source of truth for verb -> permission (shared with adapters.py)
TOOL_PERMS = {
    "filesystem": {"write": "fs:write", "delete": "fs:delete", "read": "fs:read"},
    "shell": {"run": "shell:run"},
    "http": {"request": "http:request"},
    "terraform": {"apply": "tf:apply", "plan": "tf:plan"},
    "kubernetes": {"delete": "k8s:delete", "apply": "k8s:apply"},
    "iam": {"grant": "iam:grant"},
    "monitoring": {"disable": "monitoring:disable"},
}

# (tool, verb) -> frozen gate operation
TOOL_OPERATION = {
    ("filesystem", "write"): "DB_MUTATION",
    ("filesystem", "delete"): "DB_DELETE",
    ("filesystem", "read"): "SECRET_READ",
    ("shell", "run"): "DEPLOY",
    ("http", "request"): "NET_EXPOSE",
    ("terraform", "apply"): "DEPLOY",
    ("terraform", "plan"): "DEPLOY",
    ("kubernetes", "delete"): "DB_DELETE",
    ("kubernetes", "apply"): "DEPLOY",
    ("iam", "grant"): "IAM_GRANT_ADMIN",
    ("monitoring", "disable"): "MONITORING_DISABLE",
}

DEFAULT_REVERSIBILITY = {
    "DB_MUTATION": "REVERSIBLE_WITH_COST",
    "DB_DELETE": "IRREVERSIBLE",
    "DEPLOY": "REVERSIBLE",
    "NET_EXPOSE": "REVERSIBLE",
    "SECRET_READ": "IRREVERSIBLE",
    "IAM_GRANT_ADMIN": "REVERSIBLE_WITH_COST",
    "MONITORING_DISABLE": "REVERSIBLE",
}


def needed_permission(tool: str, verb: str) -> str:
    return TOOL_PERMS[tool][verb]


def operation_for(tool: str, verb: str) -> str:
    key = (tool, verb)
    if key not in TOOL_OPERATION:
        raise KeyError(f"no operation mapping for {tool}.{verb}")
    return TOOL_OPERATION[key]


@dataclass
class ToolRequest:
    tool: str
    verb: str
    target: list
    args: dict = field(default_factory=dict)
    principal: str = "agent://sre/1"
    agent_id: str = "agent://sre/1"
    key_id: str = "k7"
    delegator: str = "user://alice"
    delegator_type: str = "HUMAN"
    objective: str = "automated infrastructure task"
    runtime: str = "gateway-runtime/1.0"
    model: str = "claude-opus-4-8"
    provider: str = "anthropic"
    grant: str = "*"                       # delegation grant (must cover permissions)
    reversibility: str | None = None       # override default per operation
    permissions: list | None = None        # override credential scope permissions
    linked_ticket: str | None = None
    attestation: dict | None = None
    rollback_plan: dict | None = None
    expected_effects: dict | None = None
    state_as_of: str | None = None         # override state freshness (for stale demos)
    correlation_id: str = "sess-gw"
    sequence_id: str = "sess-gw:0001"
    action_id: str | None = None


def build_envelope(req: ToolRequest, *, clock, policy_version: str,
                   current_state_hash: str) -> dict:
    op = operation_for(req.tool, req.verb)
    now = clock.now()
    perm = needed_permission(req.tool, req.verb)
    env = {
        "action_id": req.action_id or str(uuid.uuid4()),
        "timestamp": now,
        "agent_identity": {"id": req.agent_id, "key_id": req.key_id, "sig": "00"},
        "runtime": req.runtime,
        "model_provider": {"model": req.model, "provider": req.provider},
        "delegator": {"id": req.delegator, "type": req.delegator_type},
        "delegation_chain": [{"from": req.delegator, "to": req.agent_id,
                              "grant": req.grant, "exp": clock.plus(3600)}],
        "objective": req.objective,
        "tool": {"server_id": req.tool, "tool_name": req.verb},
        "operation": op,
        "target_resource": list(req.target),
        "arguments": dict(req.args),
        "credential_scope": {"principal": req.principal,
                             "permissions": req.permissions or [perm], "ttl": "PT5M"},
        "current_state_hash": current_state_hash,
        "state_freshness": {"as_of": req.state_as_of or now, "source": req.tool},
        "policy_version": policy_version,
        "reversibility": req.reversibility or DEFAULT_REVERSIBILITY[op],
        "correlation_id": req.correlation_id,
        "sequence_id": req.sequence_id,
    }
    if req.linked_ticket is not None:
        env["linked_ticket"] = req.linked_ticket
    if req.attestation is not None:
        env["attestation"] = req.attestation
    if req.rollback_plan is not None:
        env["rollback_plan"] = req.rollback_plan
    if req.expected_effects is not None:
        env["expected_effects"] = req.expected_effects
    return env
