"""
datasets_pressure_v2.py — composite-identity, capacity-pressured evidence task.

Design that makes CAPACITY (not template collapse or trivial matching) the cause of
plain-slot failure:

  * An early global FOCUS cue ("focus vendor V*") declares which facts are relevant.
    Detecting relevance requires the DISTANT header (global context) — a local window
    cannot see it when a far fact arrives. This is the only place a global signal
    (Phase) could help.
  * The body streams many facts, each a DISTINCT composite identity
    (contract × vendor × region × product) → distinct slots (no template collapse).
    Versions of the SAME contract supersede in-place.
  * A small set of RELEVANT facts (contracts of V*, count ≤ M-1) plus a FLOOD of
    distinct distractor contracts (other vendors). The queried contract C* is a
    relevant fact placed at a controlled target position (early / middle / late).
  * The query names C* directly, so retrieval by content works IFF C* is still in
    memory. Under the distractor flood, a model that does not prioritize the relevant
    (focus) facts evicts the early target → fails. An oracle that keeps the ≤ M-1
    focus facts retains it → the task is solvable in principle.

Pressure is defined by the number of DISTINCT LIVE CONTRACTS / M (not sentence count).
Repeated versions of one contract are supersession, not extra pressure.

Query types (Stage A validation uses `latest_value`, the cleanest capacity test):
  latest_value   : latest valid value for contract C*   (answer = value)
  source_current : source of the current value for C*    (answer = source)
  superseded_by  : version that superseded v1 of C*       (answer = version)
  relational2    : value of the contract in <region-alias> for vendor V*  (2-fact)

Leakage control: contract/vendor pools partitioned disjointly across train/val/test.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from experiments.phase_guided_slots_v2.task_schema import (
    Vocab, build_vocab, Fact, Example,
    CONTRACTS, VENDORS, REGIONS, PRODUCTS, SOURCES, EVENTS, VERSIONS, VALUES,
    RISK, APPROVAL, AUTHORITY, REGION_ALIAS,
)

TARGET_POSITIONS = ("early", "middle", "late")


def _partition(items: List[str], split: str) -> List[str]:
    n = len(items)
    return {"train": items[: int(n * 0.7)],
            "val": items[int(n * 0.7): int(n * 0.85)],
            "test": items[int(n * 0.85):]}[split]


class PressureV2Generator:
    def __init__(self, vocab: Vocab, split: str, seed: int):
        self.v = vocab
        self.split = split
        self.rng = random.Random(hash((split, "v2", seed)) & 0xFFFFFFFF)
        self.contracts = _partition(CONTRACTS, split)
        self.vendors = _partition(VENDORS, split)

    # ------------------------------------------------------------------
    def _mk_fact(self, contract: str, vendor: str, version: str, arrival: int,
                 entity_id: int) -> Fact:
        r = self.rng
        return Fact(
            contract=contract, vendor=vendor,
            region=r.choice(REGIONS), product=r.choice(PRODUCTS),
            version=version, value=r.choice(VALUES),
            source=r.choice(SOURCES), authority=r.choice(AUTHORITY),
            risk=r.choice(RISK), approval=r.choice(APPROVAL), event=r.choice(EVENTS),
            fact_id=arrival, entity_id=entity_id, relation_id=0,
            version_id=VERSIONS.index(version), source_id=SOURCES.index(r.choice(SOURCES)),
            arrival=arrival,
        )

    def make(self, n_live: int, M: int, target_position: str = "early",
             query_type: str = "latest_value", versions_per_relevant: int = 1) -> Example:
        """Build one example: `n_live` DISTINCT live contracts (one distinct slot
        each), a randomly queried target contract placed at `target_position`. The
        answer requires retrieving THAT specific contract's value — so the query and
        the bounded memory are both essential, and failure is purely capacity (the
        target is lost only if evicted). No exploitable focus/relevance structure."""
        r = self.rng
        v = self.v

        contracts_pool = r.sample(self.contracts, min(n_live, len(self.contracts)))
        need = n_live - len(contracts_pool)
        if need > 0:
            extra = [c for c in CONTRACTS if c not in contracts_pool]
            r.shuffle(extra)
            contracts_pool += extra[:need]
        all_contracts = contracts_pool[:n_live]

        # each distinct contract gets a distinct vendor cue (varied, non-diagnostic)
        vend = {c: r.choice(self.vendors) for c in all_contracts}
        eid = {c: i for i, c in enumerate(all_contracts)}

        # query a RANDOM contract (any of the live ones) — the only way to answer is to
        # have retained it and address it by the query. Nothing about the target is
        # predictable from structure, so no query-free shortcut exists.
        target_contract = r.choice(all_contracts)
        others = [c for c in all_contracts if c != target_contract]
        r.shuffle(others)

        total_units = len(all_contracts)
        if target_position == "early":
            tpos = r.randint(0, max(0, int(0.15 * total_units)))
        elif target_position == "late":
            tpos = r.randint(int(0.85 * total_units), total_units - 1)
        else:
            tpos = r.randint(int(0.40 * total_units), int(0.60 * total_units))
        order = others[:]
        order.insert(min(tpos, len(order)), target_contract)

        stream: List[Fact] = []
        for c in order:
            stream.append(self._mk_fact(c, vend[c], VERSIONS[0],
                                        arrival=len(stream), entity_id=eid[c]))
        focus_vendor = vend[target_contract]  # kept only for meta/query rendering

        # answer per query type (deterministic from the target contract's facts)
        tfacts = [f for f in stream if f.contract == target_contract]
        latest = tfacts[-1]  # latest by arrival (supersession)
        if query_type == "latest_value":
            q = ["what", "is", "the", "latest", "valid", "value", "for", "contract", target_contract]
            ans = latest.value
        elif query_type == "source_current":
            q = ["which", "source", "authorized", "the", "current", "value", "for",
                 "contract", target_contract]
            ans = latest.source
        elif query_type == "superseded_by":
            q = ["which", "version", "superseded", "version", "v1", "of", "contract", target_contract]
            ans = tfacts[1].version if len(tfacts) > 1 else latest.version
        elif query_type == "relational2":
            alias = REGION_ALIAS[latest.region]
            q = ["what", "is", "the", "value", "of", "the", "contract", "in", alias,
                 "for", "vendor", focus_vendor]
            ans = latest.value
        else:
            raise ValueError(query_type)

        # render tokens: fact stream + query + answer (no leaky header).
        # write labels: 1 at each fact's terminal <sep> (the write anchor), 0 at other
        # BODY tokens (so the gate learns to write ONCE per fact, not flood every
        # token — the flood was what collapsed v1's slots), -100 outside the body.
        words: List[str] = []
        wl: List[int] = []
        anchor_positions = []
        for f in stream:
            fw = f.render()
            for w in fw:
                words.append(w)
                if w == "<sep>":
                    wl.append(1); anchor_positions.append(len(words) - 1)
                else:
                    wl.append(0)
        toks = v.encode(words) + [v.id("<Q>")] + v.encode(q) + [v.id("<A>")]
        wl = wl + [-100] * (len(toks) - len(wl))
        ans_pos = len(toks) - 1
        ans_id = v.id(ans)
        toks.append(ans_id); wl.append(-100)

        return Example(
            tokens=toks, answer_pos=ans_pos, answer_id=ans_id, write_labels=wl,
            facts=stream, gold_support_entity_ids=[eid[target_contract]],
            query_type=query_type, target_position=target_position,
            meta={"n_live_contracts": n_live, "M": M,
                  "target_contract": target_contract,
                  "n_facts": len(stream), "seq_len": len(toks),
                  "target_entity_id": eid[target_contract],
                  "distinct_entity_ids": len(set(f.entity_id for f in stream))},
        )


def generate(vocab: Vocab, split: str, seed: int, n: int, n_live: int, M: int,
             target_mix: Optional[Dict[str, float]] = None,
             query_type: str = "latest_value") -> List[Example]:
    gen = PressureV2Generator(vocab, split, seed)
    target_mix = target_mix or {"early": 0.5, "middle": 0.25, "late": 0.25}
    out = []
    for i in range(n):
        rp = gen.rng.random()
        cum = 0.0; tp = "early"
        for pos, w in target_mix.items():
            cum += w
            if rp <= cum:
                tp = pos; break
        out.append(gen.make(n_live=n_live, M=M, target_position=tp, query_type=query_type))
    return out
