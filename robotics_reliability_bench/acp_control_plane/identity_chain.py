"""Full-chain identity binding for the AI Control Plane (V2.2 §6).

Proves that ALL layers bind to the same operation:

    context digest  ->  action hash (ActionGate)  ->  ACP candidate identity
                    ->  hypothetical execution identity

The reduced context produces a `context_digest`; the action the reader derives
from it produces ActionGate's `action_hash` and ACP's `candidate.identity`; the
execution identity is the digest of all three. `verify_chain()` fails closed on
any break — e.g. an action whose fields are not the ones carried by the surviving
context spans, or a context digest that does not match the reduced context.

The three decision schemas are NOT merged; this only *links* their identities.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Tuple


def _digest(tag: str, obj) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return tag + ":" + hashlib.sha256(payload).hexdigest()


def context_digest(*, context_id: str, base: dict, surviving_spans: list) -> str:
    """Digest over the REDUCED context actually handed to the LLM stage.

    `surviving_spans` is an ordered list of `(id, source_type, text)` tuples for
    the spans that survived compression. The digest binds the exact reduced
    context, so any change to what the LLM saw changes the whole chain.
    """
    return _digest("ctx", {
        "context_id": context_id,
        "base": base,
        "spans": [list(s) for s in surviving_spans],
    })


def proposed_action_digest(op_facts: dict) -> str:
    """Digest over the operation the reader derived from the reduced context."""
    return _digest("action", op_facts)


@dataclass(frozen=True)
class ExecutionIdentity:
    """The single identity linking every layer to one hypothetical execution."""
    context_digest: str
    proposed_action_digest: str
    actiongate_action_hash: str
    acp_candidate_identity: str

    @property
    def identity(self) -> str:
        return _digest("exec", {
            "context_digest": self.context_digest,
            "proposed_action_digest": self.proposed_action_digest,
            "actiongate_action_hash": self.actiongate_action_hash,
            "acp_candidate_identity": self.acp_candidate_identity,
        })


def verify_chain(
    *,
    reader_op_facts: dict,          # operation the reader read from the context
    stack_op_facts: dict,           # operation actually fed to ActionGate + ACP
    context_digest_value: str,
    actiongate_action_hash: str,
    acp_candidate_identity: str,
) -> Tuple[Optional[ExecutionIdentity], str]:
    """Return (ExecutionIdentity | None, reason). Fail closed on any mismatch.

    The critical check: the action ActionGate + ACP evaluated must be *exactly*
    the action the reader derived from the reduced context — otherwise a layer is
    judging a different operation than the one the context authorized.
    """
    if reader_op_facts != stack_op_facts:
        return None, "CONTEXT_TO_ACTION_MISMATCH"
    if not context_digest_value:
        return None, "MISSING_CONTEXT_DIGEST"
    if not actiongate_action_hash:
        return None, "MISSING_ACTION_HASH"
    if not acp_candidate_identity:
        return None, "MISSING_ACP_IDENTITY"
    ident = ExecutionIdentity(
        context_digest=context_digest_value,
        proposed_action_digest=proposed_action_digest(reader_op_facts),
        actiongate_action_hash=actiongate_action_hash,
        acp_candidate_identity=acp_candidate_identity)
    return ident, "BOUND"
