"""P0 base-capability suite (B1-B7). Torch-free generators + gate logic.

P0 is non-relational and uses the SAME BTRR tokenizer / ReasoningContext / serializer / output contract as
R1-R12 (Amendment 002 §9B: same tokenizer + same checkpoint for P0 and R1-R12). If P0 is not established
on a seed's frozen checkpoint, that seed's R1-R12 are stamped NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION.
"""
from __future__ import annotations

import random

from .config import P0_BLOCK_THRESHOLD, P0_SUBTASK_GATE
from .execution import assert_generation_allowed
from .generator import P0_SUBTASKS, _ID_ALPHABET, _Mint, _amount, _rng
from .schema_ext import (Constraints, Entity, Evidence, Event, ReasoningContext,
                         ReasoningOutput, ReasoningQuery)
from .serializer import assert_zero_truncation


def _entities(rng, mint, tenant, n):
    return [Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),)) for _ in range(n)]


# Preregistered B7 = "abstain with the correct status when a trivial VISIBLE flag says 'absent'" (chance 0.5).
# The flag is carried as an attribute on the queried entity under the requested property name, so the
# B1/B5 (flag PRESENT -> copy the id) and B7 (flag ABSENT -> abstain) inputs are distinguishable by one
# visible token. Without it, B7 inputs were byte-shaped identically to B1/B5 with contradictory labels.
FLAG_KEY = "target_attribute"
FLAG_PRESENT = "PRESENT"
FLAG_ABSENT = "ABSENT"


def _with_flag(e: Entity, value: str) -> Entity:
    return Entity(e.entity_type, e.entity_id, e.tenant_id, e.attributes + ((FLAG_KEY, value),))


def generate_p0_episode(subtask: str, seed: int, index: int, role: str = "unit",
                        authorization_token: str | None = None) -> ReasoningContext:
    if subtask not in P0_SUBTASKS:
        raise ValueError(f"unknown P0 subtask {subtask}")
    assert_generation_allowed(seed, authorization_token)  # fail-closed BEFORE any P0 cohort materializes
    rng = _rng(seed, "P0:" + subtask, index, role)
    tenant = "T" + "".join(rng.choice(_ID_ALPHABET) for _ in range(3))
    mint = _Mint(rng, role)
    ents = _entities(rng, mint, tenant, rng.randint(6, 12))
    events: list[Event] = []
    evd: list[Evidence] = []
    q = ReasoningQuery("resolve_attribute", "NOT_APPLICABLE", ents[0].entity_id,
                       requested_property="target_attribute")
    if subtask == "B1":                       # copy an opaque entity id (visible flag PRESENT)
        ents[0] = _with_flag(ents[0], FLAG_PRESENT)
        gold = ReasoningOutput(ents[0].entity_id, (f"Entity:{ents[0].entity_id}",), (), "SUPPORTED")
    elif subtask == "B2":                     # select one of a bounded set via a trivial cue
        target = ents[rng.randrange(len(ents))]
        ents = [Entity(e.entity_type, e.entity_id, tenant,
                       (("region", "EU"),) if e is target else (("region", "NA"),)) for e in ents]
        q = ReasoningQuery("resolve_attribute", "NOT_APPLICABLE", target.entity_id,
                           requested_property="target_attribute")
        gold = ReasoningOutput(target.entity_id, (f"Entity:{target.entity_id}",), (), "SUPPORTED")
    elif subtask == "B3":                     # copy an evidence id
        e = Entity("vendor", ents[0].entity_id, tenant)
        from .schema_ext import Relation
        rel = Relation("supplies", ents[0].entity_id, ents[1].entity_id, tenant)
        ref = mint.new()
        evd = [Evidence(ref, "supports",
                        f"{ents[0].entity_id}|supplies|{ents[1].entity_id}", tenant)]
        gold = ReasoningOutput(ref, (), (ref,), "SUPPORTED")
        return _finish(mint, tenant, q, ents, [rel], events, [], evd, gold, "P0")
    elif subtask == "B4":                     # reproduce an event id
        ev, _ = _event(rng, mint, tenant, ents[0].entity_id)
        events = [ev]
        gold = ReasoningOutput(ev.event_id, (f"Event:{ev.event_id}",), (), "SUPPORTED")
    elif subtask == "B5":                     # emit exact structured output schema (visible flag PRESENT)
        ents[0] = _with_flag(ents[0], FLAG_PRESENT)
        gold = ReasoningOutput(ents[0].entity_id, (f"Entity:{ents[0].entity_id}",), (), "SUPPORTED")
    elif subtask == "B6":                     # return a supplied categorical token
        token = ("LOW", "MEDIUM", "HIGH", "CRITICAL")[rng.randrange(4)]
        ev, _ = _event(rng, mint, tenant, ents[0].entity_id, token)
        events = [ev]
        q = ReasoningQuery("latest_event_value", "NOT_APPLICABLE", ents[0].entity_id,
                           requested_property="latest_state", event_type="risk")
        gold = ReasoningOutput(token, (f"Event:{ev.event_id}",), (), "SUPPORTED")
    else:                                     # B7 instructed trivial abstention (visible flag ABSENT)
        ents[0] = _with_flag(ents[0], FLAG_ABSENT)
        gold = ReasoningOutput(None, (), (), "INSUFFICIENT_EVIDENCE")
    return _finish(mint, tenant, q, ents, [], events, [], evd, gold, "P0")


def _event(rng, mint, tenant, entity_id, value=None):
    v = value or ("LOW", "MEDIUM", "HIGH", "CRITICAL")[rng.randrange(4)]
    ev = Event(mint.new(), entity_id, "risk", 1, v, tenant)
    return ev, v


def _finish(mint, tenant, q, ents, rels, events, pols, evd, gold, split):
    ctx = ReasoningContext(context_id=mint.new("C"), tenant_id=tenant, query=q,
                           entities=tuple(ents), relations=tuple(rels), events=tuple(events),
                           policies=tuple(pols), evidence=tuple(evd),
                           constraints=Constraints(0, False, False), authoritative_output=gold, split=split)
    assert_zero_truncation(ctx)
    return ctx


def generate_p0(subtask: str, seed: int, n: int, role: str = "unit",
                authorization_token: str | None = None) -> list[ReasoningContext]:
    assert_generation_allowed(seed, authorization_token)  # fail-closed at the P0 entry too
    return [generate_p0_episode(subtask, seed, i, role, authorization_token) for i in range(n)]


def p0_gate(subtask_accuracies: dict[str, float]) -> dict:
    """Return {'established': bool, 'per_subtask': {..pass..}, 'min_accuracy': float}.

    Established iff every B1-B7 accuracy >= P0_BLOCK_THRESHOLD (0.95). The per-subtask target is 0.98.
    """
    per = {k: {"accuracy": a, "meets_target": a >= P0_SUBTASK_GATE,
               "above_block": a >= P0_BLOCK_THRESHOLD} for k, a in subtask_accuracies.items()}
    established = bool(subtask_accuracies) and all(v["above_block"] for v in per.values())
    return {"established": established, "per_subtask": per,
            "min_accuracy": min(subtask_accuracies.values()) if subtask_accuracies else 0.0}
