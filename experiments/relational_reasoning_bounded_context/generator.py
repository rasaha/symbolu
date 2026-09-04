"""Deterministic BTRR generators for P0 (B1-B7) and R1-R12. Torch-free.

Every produced episode is a schema-valid, zero-truncation-safe ReasoningContext with a gold
ReasoningOutput derivable from the visible facts (answerable splits) or provably requiring an absent fact
(R10/R11). Determinism: RNG seeded from the (seed, split, index) triple; no wall-clock, no global RNG.

Invariants enforced/tested elsewhere: FK validity, tenant purity, completeness/absence, event & relation
order decorrelated from answer (opaque IDs), no answer-coded IDs, no policy-id->outcome leakage, disjoint
train/final identity pools by role, R12 exactly one valid path, PATH_DISCOVERY gold-path exclusion.
"""
from __future__ import annotations

import hashlib
import random
from typing import Callable

from .config import CAPS, OUTCOME_VOCAB
from .execution import assert_generation_allowed
from .schema_ext import (Condition, Constraints, Entity, Event, Evidence, Policy, Relation,
                         ReasoningContext, ReasoningOutput, ReasoningQuery)
from .serializer import assert_zero_truncation

SPLITS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12")
P0_SUBTASKS = ("B1", "B2", "B3", "B4", "B5", "B6", "B7")

_RISK = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_STATUS = ("ACTIVE", "EXPIRED", "PENDING")

# Shared identifier vocabulary. All roles draw ID *bodies* from the SAME letters, so a held-out identity
# is a new combination of TRAINED tokens (the intended unseen-identity generalization test) rather than
# never-seen characters. A role-specific trailing DIGIT (digits are well-trained tokens, seen in every
# amount/sequence) guarantees strict train/dev/final/unit pool disjointness without a token-distribution
# gap. (Earlier disjoint-*alphabet* pools made held-out eval depend on characters the model never trained
# -> 0.0 validity; this is the corrected design.)
_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_ROLE_DIGIT = {"train": "012", "dev": "345", "final": "678", "unit": "9"}
_ROLE_ALPHABET = {r: _ID_ALPHABET for r in _ROLE_DIGIT}  # back-compat: shared alphabet for all roles


def _stable_hash(text: str) -> int:
    """Process-independent string hash. Python's builtin ``hash(str)`` is salted per interpreter
    (PYTHONHASHSEED), so it must never seed a scientific RNG: the same (seed, split, index, role) would
    yield different episodes in different processes, silently breaking deterministic replay across runs."""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _rng(seed: int, split: str, index: int, role: str = "unit") -> random.Random:
    r = (int(seed) * 1_000_003 + _stable_hash(split) % 9973) * 131 + index
    return random.Random(r * 17 + (_stable_hash(role) % 7919))   # role partitions the episode/identity stream


class _Mint:
    """Opaque 6-char id minter: shared-alphabet body + role-specific trailing digit => strictly disjoint
    train/dev/final/unit pools whose tokens are all in the trained vocabulary."""

    def __init__(self, rng: random.Random, role: str) -> None:
        self.rng = rng
        self.body = _ID_ALPHABET
        self.digit = _ROLE_DIGIT.get(role, _ROLE_DIGIT["unit"])
        self.seen: set[str] = set()

    def new(self, prefix: str = "") -> str:
        while True:
            body = "".join(self.rng.choice(self.body) for _ in range(max(1, 5 - len(prefix))))
            cand = (prefix + body)[: CAPS["max_id_len"] - 1] + self.rng.choice(self.digit)
            if len(cand) >= 2 and cand not in self.seen and cand not in OUTCOME_VOCAB:
                self.seen.add(cand)
                return cand


def _amount(rng: random.Random) -> str:
    return str(rng.randint(1, 999_999_999))  # <= 9 digits


# ---------- R-split generators ----------

def _gen_direct(rng, mint, tenant, split):  # R1
    ents = [Entity("vendor", mint.new(), tenant, (("region", "EU"), ("amount", _amount(rng))))]
    for _ in range(rng.randint(5, 11)):
        ents.append(Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),)))
    root = ents[0]
    attr_v = dict(root.attributes)["region"]
    q = ReasoningQuery("resolve_attribute", "NOT_APPLICABLE", root.entity_id,
                       requested_property="target_attribute")
    gold = ReasoningOutput(attr_v, (f"Entity:{root.entity_id}",), (), "SUPPORTED")
    return ents, [], [], [], [], Constraints(0, False, False), q, gold


def _chain(rng, mint, tenant, hops):
    ents = [Entity("invoice", mint.new(), tenant, (("amount", _amount(rng)),))]
    rels = []
    rtypes = ["governed_by", "approved_vendor", "supplies"][:hops]
    types = ["contract", "vendor", "department"]
    prev = ents[0]
    for i in range(hops):
        nxt = Entity(types[i], mint.new(), tenant, (("region", "EU"),))
        ents.append(nxt)
        rels.append(Relation(rtypes[i], prev.entity_id, nxt.entity_id, tenant))
        prev = nxt
    return ents, rels, rtypes, prev


def _gen_path(rng, mint, tenant, split, given: bool, hops: int):  # R2/R3 given, R4 discovery
    ents, rels, rtypes, tail = _chain(rng, mint, tenant, hops)
    while len(ents) < rng.randint(6, 12):
        ents.append(Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),)))
        # confusable distractor relations from root to wrong targets
        if len(rels) < CAPS["max_relations"] and rng.random() < 0.5:
            rels.append(Relation(rtypes[0], ents[0].entity_id, ents[-1].entity_id, tenant))
    tail_attr = dict(tail.attributes).get("region", "EU")
    mode = "PATH_GIVEN" if given else "PATH_DISCOVERY"
    q = ReasoningQuery("resolve_path_target", mode, ents[0].entity_id,
                       relation_chain=tuple(rtypes) if given else (),
                       requested_property="target_attribute")
    path = [f"Entity:{ents[0].entity_id}"]
    prev = ents[0].entity_id
    for rt in rtypes:
        tgt = next(r.target_entity_id for r in rels if r.source_entity_id == prev and r.relation_type == rt)
        path += [f"Relation:{rt}", f"Entity:{tgt}"]
        prev = tgt
    gold = ReasoningOutput(tail_attr, tuple(path[:CAPS["max_reasoning_path_nodes"]]), (), "SUPPORTED")
    return ents, rels, [], [], [], Constraints(hops, False, False), q, gold


def _events_for(rng, mint, tenant, entity_id, etype, k, seq_start=1):
    # seq_start lets distractor entities carry HIGHER sequence numbers than the target's latest, so the
    # 'global-most-recent' shortcut (pick the newest event anywhere) is a losing strategy and temporal
    # reasoning must be entity-scoped. seq_start<=80 keeps sequences within the 2-digit cap.
    vocab = _RISK if etype == "risk" else _STATUS
    evs = [Event(mint.new(), entity_id, etype, seq_start + i, vocab[rng.randrange(len(vocab))], tenant)
           for i in range(k)]
    latest = max(evs, key=lambda e: e.sequence)
    return evs, latest


def _gen_temporal(rng, mint, tenant, split):  # R5 latest-state
    ents = [Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),))]
    evs, latest = _events_for(rng, mint, tenant, ents[0].entity_id, "risk",
                              rng.randint(CAPS["min_events_per_entity"], CAPS["max_events_per_entity"]))
    # distractor entities with their own (higher-sequence) events to defeat global-most-recent
    while len(ents) < rng.randint(6, 12):
        d = Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),))
        ents.append(d)
        de, _ = _events_for(rng, mint, tenant, d.entity_id, "risk", CAPS["max_events_per_entity"], seq_start=rng.randint(10, 80))
        evs += de
    q = ReasoningQuery("latest_event_value", "NOT_APPLICABLE", ents[0].entity_id,
                       requested_property="latest_state", event_type="risk")
    gold = ReasoningOutput(latest.value, (f"Entity:{ents[0].entity_id}", f"Event:{latest.event_id}"),
                           (), "SUPPORTED")
    return ents, [], evs[:CAPS["max_events_total"]], [], [], Constraints(0, True, False), q, gold


def _gen_rel_temporal(rng, mint, tenant, split, given: bool):  # R6 given / R7 discovery
    ents, rels, rtypes, tail = _chain(rng, mint, tenant, 2)
    evs, latest = _events_for(rng, mint, tenant, tail.entity_id, "risk", CAPS["max_events_per_entity"])
    while len(ents) < rng.randint(6, 12):
        d = Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),))
        ents.append(d)
        de, _ = _events_for(rng, mint, tenant, d.entity_id, "risk", 2, seq_start=rng.randint(10, 80))
        evs += de
    mode = "PATH_GIVEN" if given else "PATH_DISCOVERY"
    q = ReasoningQuery("path_then_latest", mode, ents[0].entity_id,
                       relation_chain=tuple(rtypes) if given else (),
                       requested_property="latest_state", event_type="risk")
    path = [f"Entity:{ents[0].entity_id}", f"Relation:{rtypes[0]}", f"Entity:{rels[0].target_entity_id}",
            f"Relation:{rtypes[1]}", f"Entity:{tail.entity_id}", f"Event:{latest.event_id}"]
    gold = ReasoningOutput(latest.value, tuple(path[:CAPS["max_reasoning_path_nodes"]]), (), "SUPPORTED")
    return ents, rels, evs[:CAPS["max_events_total"]], [], [], Constraints(2, True, False), q, gold


def _make_policy(rng, mint, tenant, latest_risk, amount_val):
    thresh = str(min(int(amount_val) - 1, 999_999_999)) if int(amount_val) > 1 else "0"
    applies = latest_risk == "HIGH" and int(amount_val) > int(thresh)
    outcome = "VP_APPROVAL_REQUIRED"
    conds = (Condition("risk", "EQ", "HIGH"), Condition("amount", "GT", thresh))
    pol = Policy(mint.new(), conds, outcome, tenant)
    # distractor policies with different outcomes (policy_id independent of outcome)
    return pol, applies, outcome


def _gen_policy(rng, mint, tenant, split):  # R8 facts pre-resolved
    amt = _amount(rng)
    ents = [Entity("vendor", mint.new(), tenant, (("risk", "HIGH"), ("amount", amt)))]
    for _ in range(rng.randint(5, 11)):
        ents.append(Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),)))
    pol, applies, outcome = _make_policy(rng, mint, tenant, "HIGH", amt)
    pols = [pol]
    for _ in range(rng.randint(0, CAPS["max_policies"] - 1)):
        pols.append(Policy(mint.new(), (Condition("risk", "EQ", "LOW"),),
                           OUTCOME_VOCAB[rng.randrange(1, len(OUTCOME_VOCAB))], tenant))
    q = ReasoningQuery("apply_policy", "NOT_APPLICABLE", ents[0].entity_id,
                       requested_property="approval_requirement", policy_scope="vendor_risk")
    gold = ReasoningOutput(outcome if applies else None,
                           (f"Entity:{ents[0].entity_id}", f"Policy:{pol.policy_id}") if applies else (),
                           (), "SUPPORTED" if applies else "POLICY_NOT_APPLICABLE")
    rng.shuffle(pols)
    return ents, [], [], pols[:CAPS["max_policies"]], [], Constraints(0, False, True), q, gold


def _gen_composite(rng, mint, tenant, split, confusable: bool):  # R9 / R12
    ents, rels, rtypes, tail = _chain(rng, mint, tenant, 2)
    amt = dict(ents[0].attributes)["amount"]
    evs, latest = _events_for(rng, mint, tenant, tail.entity_id, "risk", CAPS["max_events_per_entity"])
    # force a decisive HIGH latest for a determinate composite answer
    evs[-1] = Event(evs[-1].event_id, tail.entity_id, "risk", max(e.sequence for e in evs), "HIGH", tenant)
    latest = evs[-1]
    pol, _, outcome = _make_policy(rng, mint, tenant, "HIGH", amt)
    pols = [pol]
    # distractors / confusables
    ndist = rng.randint(4, 8) if confusable else rng.randint(3, 6)
    while len(ents) < min(CAPS["max_entities"], 4 + ndist):
        d = Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),))
        ents.append(d)
        de, _ = _events_for(rng, mint, tenant, d.entity_id, "risk", 2, seq_start=rng.randint(10, 80))
        evs += de
        if confusable and len(rels) < CAPS["max_relations"]:
            rels.append(Relation(rtypes[0], ents[0].entity_id, d.entity_id, tenant))  # wrong branch, dead-ends
    for _ in range(rng.randint(0, 2)):
        if len(pols) < CAPS["max_policies"]:
            pols.append(Policy(mint.new(), (Condition("risk", "EQ", "LOW"),),
                               OUTCOME_VOCAB[rng.randrange(1, len(OUTCOME_VOCAB))], tenant))
    evd = [Evidence(mint.new(), "supports", latest.event_id, tenant),
           Evidence(mint.new(), "supports",
                    f"{ents[0].entity_id}|{rtypes[0]}|{rels[0].target_entity_id}", tenant)]
    q = ReasoningQuery("apply_policy", "PATH_DISCOVERY", ents[0].entity_id,
                       requested_property="approval_requirement", policy_scope="vendor_risk",
                       event_type="risk")
    path = [f"Entity:{ents[0].entity_id}", f"Relation:{rtypes[0]}", f"Entity:{rels[0].target_entity_id}",
            f"Relation:{rtypes[1]}", f"Entity:{tail.entity_id}", f"Event:{latest.event_id}",
            f"Policy:{pol.policy_id}"]
    gold = ReasoningOutput(outcome, tuple(path[:CAPS["max_reasoning_path_nodes"]]),
                           tuple(e.evidence_ref for e in evd), "SUPPORTED")
    rng.shuffle(pols)
    return (ents[:CAPS["max_entities"]], rels[:CAPS["max_relations"]], evs[:CAPS["max_events_total"]],
            pols[:CAPS["max_policies"]], evd[:CAPS["max_evidence"]], Constraints(2, True, True), q, gold)


def _gen_r10(rng, mint, tenant, split):
    """R10 AUTHORIZED_ABSENCE: the necessary fact is UNAVAILABLE in the authorized working set. The root
    invoice has NO relation/path to any vendor-risk at all (the required fact is genuinely absent).
    Unauthorized/cross-tenant data stays completely model-invisible (tenant purity holds by construction).
    Length-preserving via distractor vendors/events/relations that never connect to the root."""
    root = Entity("invoice", mint.new(), tenant, (("amount", _amount(rng)),))
    ents = [root]
    rels: list[Relation] = []
    evs: list[Event] = []
    for _ in range(rng.randint(5, 9)):
        d = Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),))
        ents.append(d)
        evs += _events_for(rng, mint, tenant, d.entity_id, "risk", CAPS["max_events_per_entity"])[0]
    dvend = [e for e in ents if e.entity_type == "vendor"]
    for _ in range(rng.randint(2, min(CAPS["max_relations"], 8))):
        a, b = rng.sample(dvend, 2)
        r = Relation("supplies", a.entity_id, b.entity_id, tenant)   # never from the root invoice
        if r.key() not in {x.key() for x in rels}:
            rels.append(r)
    pols = [Policy(mint.new(), (Condition("risk", "EQ", "LOW"),),
                   OUTCOME_VOCAB[rng.randrange(1, len(OUTCOME_VOCAB))], tenant)]
    q = ReasoningQuery("apply_policy", "PATH_DISCOVERY", root.entity_id,
                       requested_property="approval_requirement", policy_scope="vendor_risk",
                       event_type="risk")
    gold = ReasoningOutput(None, (), (), "INSUFFICIENT_EVIDENCE")
    return (ents[:CAPS["max_entities"]], rels[:CAPS["max_relations"]], evs[:CAPS["max_events_total"]],
            pols[:CAPS["max_policies"]], [], Constraints(2, True, True), q, gold)


def _gen_r11(rng, mint, tenant, split):
    """R11 INSUFFICIENT_EVIDENCE: the relevant entity/path DOES exist (root invoice -> contract -> vendor
    with risk events, so the vendor's latest risk is knowable), but the required SUPPORTING policy is
    deliberately MISSING (no policy covers the approval question), so the conclusion is not supported.
    Distinct construction from R10 (there the path itself is absent)."""
    ents, rels, rtypes, tail = _chain(rng, mint, tenant, 2)          # root DOES connect to a vendor
    evs, _ = _events_for(rng, mint, tenant, tail.entity_id, "risk", CAPS["max_events_per_entity"])
    while len(ents) < rng.randint(6, 10):
        d = Entity("vendor", mint.new(), tenant, (("amount", _amount(rng)),))
        ents.append(d)
        evs += _events_for(rng, mint, tenant, d.entity_id, "risk", 2)[0]
    # NO applicable policy is supplied (only an off-topic LOW-risk policy) -> approval unsupported
    pols = [Policy(mint.new(), (Condition("status", "EQ", "ACTIVE"),),
                   OUTCOME_VOCAB[rng.randrange(1, len(OUTCOME_VOCAB))], tenant)]
    q = ReasoningQuery("apply_policy", "PATH_DISCOVERY", ents[0].entity_id,
                       requested_property="approval_requirement", policy_scope="vendor_risk",
                       event_type="risk")
    gold = ReasoningOutput(None, (), (), "INSUFFICIENT_EVIDENCE")
    return (ents[:CAPS["max_entities"]], rels[:CAPS["max_relations"]], evs[:CAPS["max_events_total"]],
            pols[:CAPS["max_policies"]], [], Constraints(2, True, True), q, gold)


_DISPATCH: dict[str, Callable] = {
    "R1": lambda r, m, t, s: _gen_direct(r, m, t, s),
    "R2": lambda r, m, t, s: _gen_path(r, m, t, s, True, 1),
    "R3": lambda r, m, t, s: _gen_path(r, m, t, s, True, r.randint(2, 3)),
    "R4": lambda r, m, t, s: _gen_path(r, m, t, s, False, r.randint(2, 3)),
    "R5": lambda r, m, t, s: _gen_temporal(r, m, t, s),
    "R6": lambda r, m, t, s: _gen_rel_temporal(r, m, t, s, True),
    "R7": lambda r, m, t, s: _gen_rel_temporal(r, m, t, s, False),
    "R8": lambda r, m, t, s: _gen_policy(r, m, t, s),
    "R9": lambda r, m, t, s: _gen_composite(r, m, t, s, False),
    "R10": lambda r, m, t, s: _gen_r10(r, m, t, s),
    "R11": lambda r, m, t, s: _gen_r11(r, m, t, s),
    "R12": lambda r, m, t, s: _gen_composite(r, m, t, s, True),
}


def generate_episode(split: str, seed: int, index: int, role: str = "unit",
                     authorization_token: str | None = None) -> ReasoningContext:
    if split not in _DISPATCH:
        raise ValueError(f"unknown split {split}")
    assert_generation_allowed(seed, authorization_token)  # fail-closed BEFORE any cohort materializes
    rng = _rng(seed, split, index, role)
    tenant = "T" + "".join(rng.choice(_ID_ALPHABET) for _ in range(3))
    mint = _Mint(rng, role)
    ents, rels, evs, pols, evd, cons, q, gold = _DISPATCH[split](rng, mint, tenant, split)
    ctx = ReasoningContext(context_id=mint.new("C"), tenant_id=tenant, query=q,
                           entities=tuple(ents), relations=tuple(rels), events=tuple(evs),
                           policies=tuple(pols), evidence=tuple(evd), constraints=cons,
                           authoritative_output=gold, split=split)
    assert_zero_truncation(ctx)  # never truncate; reject over-cap by raising
    return ctx


def generate_split(split: str, seed: int, n: int, role: str = "unit",
                   authorization_token: str | None = None) -> list[ReasoningContext]:
    assert_generation_allowed(seed, authorization_token)  # fail-closed at the split entry too
    return [generate_episode(split, seed, i, role, authorization_token) for i in range(n)]
