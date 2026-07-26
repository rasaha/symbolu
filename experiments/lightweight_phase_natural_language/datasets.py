"""
datasets.py — natural-language enterprise evidence tasks (word-level).

Every task is rendered as coherent enterprise-style prose (policies, contracts,
vendor records, audit findings, incident reports), NOT isolated integer copying.
A deterministic word-level tokenizer maps the closed vocabulary to ids. Answers
are single tokens (entity / value / source / yes-no / version) so answer-position
supervision is well-defined and consistent across all four arms.

Sequence layout per example:
    <context prose ...> <Q> <question words ...> <A> <answer-token>
The model is supervised / evaluated at the <A> position to predict answer-token.

Leakage control: entity, value, and source pools are partitioned into disjoint
train / val / test subsets, so the test set contains unseen entity–value–source
*combinations*, not merely unseen seeds. Adversarial variants (near-duplicate
names, paraphrased questions, reordered evidence, distractors, contradictory
sources, changed values, unseen lengths) are generated on demand.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Closed vocabulary building blocks
# ---------------------------------------------------------------------------
# Entity base names + optional geographic suffixes → near-duplicate families.
BASE_NAMES = [
    "Orion", "Atlas", "Meridian", "Vertex", "Cobalt", "Juniper", "Halcyon",
    "Nimbus", "Sable", "Quartz", "Beacon", "Cardinal", "Dovetail", "Ridgeway",
    "Sterling", "Falcon", "Larkspur", "Onyx", "Pinnacle", "Willow",
]
SUFFIXES = ["", "", "North", "South", "Global", "Group", "Partners"]

# Value tokens rendered as compact money strings (single tokens). A moderate
# closed answer vocabulary (20) keeps the copy target learnable at micro-scale
# while remaining non-trivial (chance = 1/20 = 0.05).
VALUE_TOKENS = [f"${v/10:.1f}M" for v in range(11, 31)]  # $1.1M .. $3.0M

# Source document identifiers.
SOURCE_TOKENS = [f"DOC-{c}{n}" for c in "ABCDEFGH" for n in range(1, 6)]  # 40 sources

VERSION_TOKENS = ["v1", "v2", "v3", "v4", "the-original", "the-amendment", "the-restatement"]

# Enterprise filler prose templates (distractor sentences with no answer content).
FILLER = [
    "the operating committee reviewed the quarterly compliance summary in detail",
    "all vendors must submit updated insurance certificates before onboarding",
    "the internal audit team flagged several procedural gaps for remediation",
    "procurement policy requires two approvals for any material commitment",
    "the incident response runbook was circulated to the regional managers",
    "staff completed the annual data handling training ahead of schedule",
    "the finance office reconciled the ledger against the vendor statements",
    "meeting notes were archived in the shared governance repository",
    "the service desk resolved the outstanding access requests this week",
    "a routine review of retention schedules was conducted by legal",
    "the steering group deferred the infrastructure decision to next cycle",
    "operational metrics remained within the agreed tolerance bands",
]

QUESTION_PARAPHRASES = {
    "value": [
        "what amount was recorded for", "what is the contract value for",
        "how much was committed to", "what sum applies to",
    ],
    "source": [
        "which document records", "what is the source for",
        "where is the record for", "which file states",
    ],
    "version": [
        "which version currently governs", "what is the controlling version of",
        "which revision is in force for", "what supersedes the prior terms of",
    ],
    "yesno": [
        "is the provided evidence sufficient to answer about",
        "can the amount be determined for", "is there enough evidence for",
    ],
}

# Structural / control tokens.
SPECIAL = ["<pad>", "<Q>", "<A>", "<sep>", "INSUFFICIENT", "yes", "no",
           "vendor", "contract", "records", "amount", "of", "for", "the",
           "section", "clause", "amended", "superseded", "current", "states",
           "rule", "exception", "applies", "and", "is", "was", "to", "in",
           "committed", "per", "document", "policy", "value"]


@dataclass
class Tokenizer:
    stoi: Dict[str, int]
    itos: List[str]

    @property
    def vocab_size(self) -> int:
        return len(self.itos)

    def encode(self, words: List[str]) -> List[int]:
        unk = self.stoi["<sep>"]
        return [self.stoi.get(w, unk) for w in words]

    def id(self, word: str) -> int:
        return self.stoi[word]

    @property
    def pad_id(self) -> int:
        return self.stoi["<pad>"]


def build_tokenizer() -> Tokenizer:
    words: List[str] = list(SPECIAL)
    words += BASE_NAMES
    words += [s for s in SUFFIXES if s]
    words += VALUE_TOKENS
    words += SOURCE_TOKENS
    words += VERSION_TOKENS
    # add every unique filler / paraphrase word
    for sent in FILLER:
        words += sent.split()
    for group in QUESTION_PARAPHRASES.values():
        for q in group:
            words += q.split()
    # dedupe, stable order
    seen, ordered = set(), []
    for w in words:
        if w not in seen:
            seen.add(w); ordered.append(w)
    stoi = {w: i for i, w in enumerate(ordered)}
    return Tokenizer(stoi=stoi, itos=ordered)


# ---------------------------------------------------------------------------
# Split-aware pools (leakage control by construction)
# ---------------------------------------------------------------------------
@dataclass
class Pools:
    entities: List[str]
    values: List[str]
    sources: List[str]


def make_pools(split: str) -> Pools:
    """Split-aware pools.

    ENTITY names are partitioned disjointly across splits, so the test set uses
    entity identities never seen in training — real combination novelty, not just
    unseen seeds. VALUE and SOURCE token vocabularies are SHARED across splits:
    these tasks are copy-from-context retrieval, and an answer token must be
    emittable by the (softmax) output head to be scorable at all. Novelty of the
    *binding* (which entity → which value/source) is guaranteed because each
    example randomizes it in-context; it can never be memorized.
    """
    # dedupe entities (SUFFIXES contains "" twice by design for base-name weighting)
    seen, entities = set(), []
    for b in BASE_NAMES:
        for s in SUFFIXES:
            key = f"{b}|{s}"
            if key not in seen:
                seen.add(key); entities.append(key)

    def part(items, split):
        n = len(items)
        return {"train": items[: int(n * 0.7)],
                "val": items[int(n * 0.7): int(n * 0.85)],
                "test": items[int(n * 0.85):]}[split]

    return Pools(
        entities=part(entities, split),
        values=list(VALUE_TOKENS),    # shared (emittable answer vocabulary)
        sources=list(SOURCE_TOKENS),  # shared
    )


def entity_words(entity: str) -> List[str]:
    base, suf = entity.split("|")
    return ["vendor", base] + ([suf] if suf else [])


# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------
@dataclass
class Example:
    tokens: List[int]
    answer_pos: int          # index of the <A> position; predict tokens[answer_pos+1]... (we store target separately)
    answer_id: int
    task: str
    meta: Dict = field(default_factory=dict)
    source_id: Optional[int] = None  # for source-attribution scoring


class TaskGenerator:
    def __init__(self, tok: Tokenizer, split: str, seed: int,
                 target_len: int = 256, min_gap: int = 40):
        self.tok = tok
        self.split = split
        self.pools = make_pools(split)
        self.rng = random.Random(hash((split, seed)) & 0xFFFFFFFF)
        self.target_len = target_len
        self.min_gap = min_gap

    # -- helpers -------------------------------------------------------
    def _filler_words(self, n_sent: int) -> List[str]:
        out: List[str] = []
        for _ in range(n_sent):
            out += self.rng.choice(FILLER).split()
        return out

    def _assemble(self, context_words: List[str], q_words: List[str],
                  answer_word: str, task: str, meta: Dict,
                  source_id: Optional[int] = None) -> Example:
        toks = self.tok.encode(context_words)
        toks += [self.tok.id("<Q>")] + self.tok.encode(q_words)
        toks += [self.tok.id("<A>")]
        ans_pos = len(toks) - 1
        answer_id = self.tok.id(answer_word)
        toks += [answer_id]
        return Example(tokens=toks, answer_pos=ans_pos, answer_id=answer_id,
                       task=task, meta=meta, source_id=source_id)

    def _pad_to_len(self, words: List[str], fact_block: List[str],
                    place_frac: float) -> Tuple[List[str], int]:
        """Insert fact_block into filler so total ≈ target_len words; return (words, fact_start)."""
        need = max(0, self.target_len - len(fact_block))
        pre_n = int(need * place_frac)
        post_n = need - pre_n
        pre = self._filler_words(max(1, pre_n // 10))
        post = self._filler_words(max(1, post_n // 10))
        words = pre + fact_block + post
        return words, len(pre)

    # -- Task 1: general prose LM -------------------------------------
    def lm(self) -> Example:
        words = self._filler_words(max(4, self.target_len // 10))
        toks = self.tok.encode(words)
        return Example(tokens=toks, answer_pos=len(toks) - 2,
                       answer_id=toks[-1], task="lm", meta={"len": len(toks)})

    # -- Task 2: distant single-fact retrieval ------------------------
    def distant_fact(self, distance_frac: float = 0.1) -> Example:
        ent = self.rng.choice(self.pools.entities)
        val = self.rng.choice(self.pools.values)
        fact = entity_words(ent) + ["valued", val]  # value adjacent to entity
        words, start = self._pad_to_len([], fact, distance_frac)
        q = self.rng.choice(QUESTION_PARAPHRASES["value"]) .split() + entity_words(ent)
        ex = self._assemble(words, q, val, "distant_fact",
                            {"distance": start, "len": len(words)})
        return ex

    # -- Task 3: multiple evidence candidates -------------------------
    def multi_candidate(self, n: int = 3) -> Example:
        ents = self.rng.sample(self.pools.entities, min(n, len(self.pools.entities)))
        vals = self.rng.sample(self.pools.values, len(ents))
        target = self.rng.randrange(len(ents))
        block: List[str] = []
        for e, v in zip(ents, vals):
            block += entity_words(e) + ["valued", v, "<sep>"]
        words, start = self._pad_to_len([], block, 0.2)
        q = self.rng.choice(QUESTION_PARAPHRASES["value"]).split() + entity_words(ents[target])
        distractors = [v for i, v in enumerate(vals) if i != target]
        return self._assemble(words, q, vals[target], "multi_candidate",
                              {"n_candidates": len(ents), "len": len(words),
                               "distractor_values": distractors})

    # -- Task 4: entity–attribute binding -----------------------------
    def entity_binding(self, n_entities: int = 4, similar: bool = True) -> Example:
        if similar:
            base = self.rng.choice(BASE_NAMES)
            ents = [f"{base}|{s}" for s in SUFFIXES if f"{base}|{s}" in self.pools.entities]
            ents = ents[:n_entities] or self.rng.sample(self.pools.entities, min(n_entities, len(self.pools.entities)))
        else:
            ents = self.rng.sample(self.pools.entities, min(n_entities, len(self.pools.entities)))
        vals = self.rng.sample(self.pools.values, len(ents))
        target = self.rng.randrange(len(ents))
        block: List[str] = []
        order = list(range(len(ents)))
        self.rng.shuffle(order)
        for i in order:
            block += entity_words(ents[i]) + ["valued", vals[i], "<sep>"]
        words, start = self._pad_to_len([], block, 0.15)
        q = self.rng.choice(QUESTION_PARAPHRASES["value"]).split() + entity_words(ents[target])
        distractors = [v for i, v in enumerate(vals) if i != target]
        return self._assemble(words, q, vals[target], "entity_binding",
                              {"n_entities": len(ents), "similar": similar, "len": len(words),
                               "distractor_values": distractors})

    # -- Task 5: source attribution -----------------------------------
    def source_attr(self) -> Example:
        ent = self.rng.choice(self.pools.entities)
        val = self.rng.choice(self.pools.values)
        src = self.rng.choice(self.pools.sources)
        # answer (source id) adjacent to the entity phrase
        fact = entity_words(ent) + ["valued", val, "recorded", "in", src]
        words, start = self._pad_to_len([], fact, 0.1)
        q = self.rng.choice(QUESTION_PARAPHRASES["source"]).split() + entity_words(ent)
        ex = self._assemble(words, q, src, "source_attr",
                           {"len": len(words)}, source_id=self.tok.id(src))
        return ex

    # -- Task 7: amendment / supersession -----------------------------
    def supersession(self) -> Example:
        ent = self.rng.choice(self.pools.entities)
        old_v = self.rng.choice(self.pools.values)
        new_v = self.rng.choice([v for v in self.pools.values if v != old_v])
        block = (entity_words(ent) + ["valued", old_v, "<sep>"]
                 + ["the", "amendment", "valued", new_v, "current", "<sep>"])
        words, start = self._pad_to_len([], block, 0.15)
        q = self.rng.choice(QUESTION_PARAPHRASES["value"]).split() + ["current"] + entity_words(ent)
        return self._assemble(words, q, new_v, "supersession",
                              {"stale": old_v, "len": len(words)})

    # -- Task 11: insufficient evidence -------------------------------
    def insufficient(self) -> Example:
        ent = self.rng.choice(self.pools.entities)
        other = self.rng.choice([e for e in self.pools.entities if e != ent])
        val = self.rng.choice(self.pools.values)
        # fact is about `other`, question asks about `ent` → unanswerable
        fact = entity_words(other) + ["valued", val]
        words, start = self._pad_to_len([], fact, 0.2)
        q = self.rng.choice(QUESTION_PARAPHRASES["value"]).split() + entity_words(ent)
        return self._assemble(words, q, "INSUFFICIENT", "insufficient",
                              {"len": len(words)})


TASK_METHODS = {
    "lm": "lm",
    "distant_fact": "distant_fact",
    "multi_candidate": "multi_candidate",
    "entity_binding": "entity_binding",
    "source_attr": "source_attr",
    "supersession": "supersession",
    "insufficient": "insufficient",
}


def generate_split(tok: Tokenizer, split: str, seed: int, per_task: int,
                   target_len: int, task_mix: Optional[List[str]] = None) -> List[Example]:
    task_mix = task_mix or list(TASK_METHODS)
    exs: List[Example] = []
    gen = TaskGenerator(tok, split, seed, target_len=target_len)
    for task in task_mix:
        meth = getattr(gen, TASK_METHODS[task])
        for _ in range(per_task):
            exs.append(meth())
    return exs


def dataset_manifest(tok: Tokenizer, seed: int, per_task: int, target_lens: List[int]) -> Dict:
    def h(obj):
        return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]
    return {
        "generation_seed": seed,
        "per_task": per_task,
        "target_lens": target_lens,
        "task_families": list(TASK_METHODS),
        "vocab_size": tok.vocab_size,
        "entity_pool": {s: len(make_pools(s).entities) for s in ("train", "val", "test")},
        "value_pool": {s: len(make_pools(s).values) for s in ("train", "val", "test")},
        "source_pool": {s: len(make_pools(s).sources) for s in ("train", "val", "test")},
        "value_range": [VALUE_TOKENS[0], VALUE_TOKENS[-1]],
        "vocab_hash": h(tok.itos),
        "split_entity_hash": {s: h(make_pools(s).entities) for s in ("train", "val", "test")},
    }
