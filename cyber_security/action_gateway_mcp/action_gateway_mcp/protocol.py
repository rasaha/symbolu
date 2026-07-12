"""MCP-style protocol parsing + frozen-outcome -> protocol-response mapping.

A minimal JSON-RPC-shaped envelope is used (``method`` = ``tools/list`` |
``tools/call``); the transport specifics are intentionally thin so a non-MCP
adapter (HTTP/gRPC) can reuse the same server core. This module contains no
enforcement logic.
"""

from __future__ import annotations

from .errors import ProtocolError

# frozen decision outcomes
ALLOW = "ALLOW"
ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
SIMULATE_AND_RETRY = "SIMULATE_AND_RETRY"
REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
DENY = "DENY"

EXECUTABLE = frozenset({ALLOW, ALLOW_WITH_CONSTRAINTS})

# outcome -> (executable, machine-readable next action)
_NEXT = {
    ALLOW: (True, "EXECUTE"),
    ALLOW_WITH_CONSTRAINTS: (True, "EXECUTE_WITH_CONSTRAINTS"),
    SIMULATE_AND_RETRY: (False, "PROVIDE_SIMULATION"),
    REQUEST_MORE_EVIDENCE: (False, "PROVIDE_EVIDENCE"),
    ESCALATE_TO_HUMAN: (False, "OBTAIN_HUMAN_APPROVAL"),
    DENY: (False, "NONE"),
}


def parse_request(payload: dict) -> dict:
    """Validate the JSON-RPC-ish shape; return {method, name, arguments, meta, id}."""
    if not isinstance(payload, dict):
        raise ProtocolError("request must be a JSON object")
    if payload.get("jsonrpc") != "2.0":
        raise ProtocolError("unsupported or missing jsonrpc version")
    method = payload.get("method")
    if method not in ("tools/list", "tools/call"):
        raise ProtocolError(f"unsupported method {method!r}")
    params = payload.get("params") or {}
    meta = params.get("_meta") or {}
    out = {"id": payload.get("id"), "method": method, "meta": meta}
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ProtocolError("tools/call requires params.name")
        args = params.get("arguments")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ProtocolError("params.arguments must be an object")
        out["name"] = name
        out["arguments"] = args
    return out


def decision_response(*, outcome, request_id, action_hash, dispositive_rules,
                      applied_constraints, reason, required_evidence=None,
                      required_next=None, escalation_id=None) -> dict:
    """Structured protocol response for any of the six outcomes. Never carries a token."""
    executable, next_action = _NEXT[outcome]
    resp = {
        "outcome": outcome,
        "executable": executable,
        "next_action": required_next or next_action,
        "request_id": request_id,
        "action_hash": action_hash,
        "dispositive_rules": dispositive_rules,
        "reason_codes": [reason] if reason else list(dispositive_rules),
        "applied_constraints": applied_constraints,
        # a protocol response is never itself execution authority:
        "execution_token": None,
    }
    if required_evidence:
        resp["required_evidence"] = list(required_evidence)
    if escalation_id:
        resp["escalation_id"] = escalation_id
    return resp
