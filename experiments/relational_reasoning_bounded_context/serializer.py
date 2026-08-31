"""Compact deterministic BTRR serializer + zero-truncation guard. Torch-free.

Model-visible input only (gold output is never serialized). Records are emitted in an order determined by
opaque IDs (entity_id, relation key, event_id, policy_id, evidence_ref) which the generator assigns
decorrelated from sequence/path/answer — so serialization order encodes neither the latest event nor the
gold path.
"""
from __future__ import annotations

from .config import INPUT_TOKEN_LIMIT, MAX_SEQ_LEN, OUTPUT_TOKEN_LIMIT
from .schema_ext import ReasoningContext, ReasoningOutput
from .tokenizer import BTRRTokenizer

_TOK = BTRRTokenizer()


class TruncationError(ValueError):
    """Raised if any legal-serialized episode would exceed a frozen token limit (never truncate)."""


def serialize_input(ctx: ReasoningContext) -> str:
    q = ctx.query
    lines: list[str] = [f"CTX {ctx.tenant_id}"]
    qparts = ["QRY", q.operation, q.path_mode, q.root_entity_id]
    if q.requested_property:
        qparts.append(q.requested_property)
    if q.policy_scope:
        qparts.append(q.policy_scope)
    if q.event_type:
        qparts.append(q.event_type)
    if q.path_mode == "PATH_GIVEN":
        qparts.extend(q.relation_chain)
    lines.append(" ".join(qparts))
    for e in sorted(ctx.entities, key=lambda x: x.entity_id):
        row = ["ENT", e.entity_type, e.entity_id]
        for k, v in e.attributes:
            row.extend([k, v])
        lines.append(" ".join(row))
    for r in sorted(ctx.relations, key=lambda x: x.key()):
        lines.append(f"REL {r.source_entity_id} {r.relation_type} {r.target_entity_id}")
    for ev in sorted(ctx.events, key=lambda x: x.event_id):
        lines.append(f"EVT {ev.event_id} {ev.entity_id} {ev.event_type} {ev.sequence} {ev.value}")
    for p in sorted(ctx.policies, key=lambda x: x.policy_id):
        row = [f"POL {p.policy_id}"]
        for c in p.conditions:
            row.append(f"COND {c.field_name} {c.operator} {c.literal}")
        row.append(f"OUT {p.outcome}")
        lines.append(" ".join(row))
    for ev in sorted(ctx.evidence, key=lambda x: x.evidence_ref):
        lines.append(f"EVD {ev.evidence_ref} {ev.stance} {ev.supports_ref}")
    return "\n".join(lines) + "\n"


def input_token_count(ctx: ReasoningContext) -> int:
    return _TOK.count(serialize_input(ctx), add_bos=True)


def output_token_count(out: ReasoningOutput) -> int:
    from .output import serialize_output
    return _TOK.count(serialize_output(out), add_bos=False, add_eos=True)


def assert_zero_truncation(ctx: ReasoningContext) -> dict[str, int]:
    """Prove input <= 3520, output <= 384, input+output <= 3904 for this episode. Raise otherwise."""
    it = input_token_count(ctx)
    ot = output_token_count(ctx.authoritative_output)
    if it > INPUT_TOKEN_LIMIT:
        raise TruncationError(f"input {it} > input_token_limit {INPUT_TOKEN_LIMIT}")
    if ot > OUTPUT_TOKEN_LIMIT:
        raise TruncationError(f"output {ot} > output_token_limit {OUTPUT_TOKEN_LIMIT}")
    if it + ot > MAX_SEQ_LEN:
        raise TruncationError(f"input+output {it + ot} > max_seq_len {MAX_SEQ_LEN}")
    return {"input_tokens": it, "output_tokens": ot, "combined": it + ot}
