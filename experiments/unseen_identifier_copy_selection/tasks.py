"""Deterministic C1-C8 example construction for the unseen-identifier diagnostic.

Every generator is a pure function of (split, cohort, seed); repeated calls are byte-identical.
No reserved cohort is generated here (callers pass the cohort/seed; reserved seeds are gated by
`execution.require_execution_authorization`). No constant-gold component enters the primary
competence score: C8 (abstention) is a separate split, and positive splits require reading the
queried fact from context.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field

from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer

from .config import (
    ABSTENTION_TOKEN,
    CANDIDATE_COUNT,
    EXAMPLES_PER_SPLIT,
    IDENTIFIER_ALPHABET,
    IDENTIFIER_LENGTH,
    POSITIONS,
    sub_seed,
)
from .identifiers import (
    assert_character_visible,
    assert_collision_free,
    assert_pools_disjoint,
    build_pools,
)

_PER_SPLIT_WINDOW = 512
_EVIDENCE_WINDOW = 256

# frozen task names emitted in the serialized `TASK =` field
TASK_NAME = {
    "C1": "DIRECT_COPY", "C2": "RELATION_LOOKUP", "C3": "EVIDENCE_LOOKUP", "C4": "RELATION_LOOKUP",
    "C5": "RELATION_LOOKUP", "C6": "RELATION_LOOKUP", "C7": "RELATION_LOOKUP", "C8": "MISSING_KEY",
}


@dataclass(frozen=True)
class Example:
    split: str
    cohort: str
    base_seed: int
    derived_sub_seed: int
    index: int
    task_name: str
    query_source: str | None
    query_target: str | None            # C3 only (the queried relation's target)
    pairs: tuple[tuple[str, str], ...]  # FACTS source->target pairs (empty for C1)
    pair_evidence: tuple[str, ...]      # C3: evidence id per pair (empty otherwise)
    target_id: str | None               # C1 direct target
    candidate_ids: tuple[str, ...]      # answer candidates (targets, or evidence for C3)
    correct_position: int | None
    evidence_id: str | None
    context_ids: tuple[str, ...]        # every identifier visible in the serialized context
    seen_unseen: str
    tokenizer_length: int
    lexical_decoy_class: str
    expected_output: str
    expected_abstention: bool
    example_hash: str = field(default="", compare=False)

    def with_hash(self) -> "Example":
        payload = json.dumps(
            {
                "split": self.split, "cohort": self.cohort, "index": self.index,
                "task_name": self.task_name, "query_source": self.query_source,
                "query_target": self.query_target, "pairs": [list(p) for p in self.pairs],
                "pair_evidence": list(self.pair_evidence), "target_id": self.target_id,
                "candidate_ids": list(self.candidate_ids), "correct_position": self.correct_position,
                "evidence_id": self.evidence_id, "seen_unseen": self.seen_unseen,
                "lexical_decoy_class": self.lexical_decoy_class,
                "expected_output": self.expected_output, "expected_abstention": self.expected_abstention,
            },
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")
        object.__setattr__(self, "example_hash", hashlib.sha256(payload).hexdigest())
        return self


def _lexical_neighbor(rng: random.Random, base: str, edits: int) -> str:
    chars = list(base)
    for p in rng.sample(range(IDENTIFIER_LENGTH), k=min(edits, IDENTIFIER_LENGTH)):
        alt = rng.choice(IDENTIFIER_ALPHABET)
        while alt == chars[p]:
            alt = rng.choice(IDENTIFIER_ALPHABET)
        chars[p] = alt
    return "".join(chars)


def generate_split(split: str, cohort: str, seed: int, n: int = EXAMPLES_PER_SPLIT) -> list[Example]:
    if split not in TASK_NAME:
        raise ValueError(f"unknown split: {split}")
    if cohort not in ("seen", "unseen"):
        raise ValueError(f"unknown cohort: {cohort} (use 'seen' or 'unseen')")
    tokenizer = LexicalTokenizer()
    ds = sub_seed(int(seed), "dataset") * 17 + int(split[1:])
    rng = random.Random(ds)
    # Disjoint master pools (train/final/evidence disjoint by construction); each split takes its
    # own non-overlapping window so splits never share identifiers.
    master = build_pools(seed, per_split_window=_PER_SPLIT_WINDOW, evidence_window=_EVIDENCE_WINDOW)
    idx = int(split[1:]) - 1
    base = master["train"] if cohort == "seen" else master["final"]
    pool = base[idx * _PER_SPLIT_WINDOW:(idx + 1) * _PER_SPLIT_WINDOW]
    epool = master["evidence"][idx * _EVIDENCE_WINDOW:(idx + 1) * _EVIDENCE_WINDOW]
    if n * (CANDIDATE_COUNT + 3) > len(pool):
        raise ValueError("requested example count exceeds the per-split identifier window")
    assert_collision_free(pool)
    assert_collision_free(epool)
    assert_pools_disjoint(ids=pool, evidence=epool)
    assert_character_visible(pool[: min(len(pool), 16)], tokenizer)

    cursor = ecursor = 0

    def take(k: int) -> list[str]:
        nonlocal cursor
        chunk = list(pool[cursor:cursor + k]); cursor += k
        return chunk

    def take_ev(k: int) -> list[str]:
        nonlocal ecursor
        chunk = list(epool[ecursor:ecursor + k]); ecursor += k
        return chunk

    name = TASK_NAME[split]
    out: list[Example] = []
    for i in range(n):
        pos = i % len(POSITIONS)
        if split == "C1":
            target = take(1)[0]
            ex = Example(split, cohort, int(seed), ds, i, name, None, None, (), (), target,
                         (), None, None, (target,), cohort, IDENTIFIER_LENGTH, "none", target, False)
        elif split in ("C2", "C4", "C6", "C7"):
            sources = take(CANDIDATE_COUNT); targets = take(CANDIDATE_COUNT)
            correct = pos if split == "C4" else rng.randrange(CANDIDATE_COUNT)
            pairs = tuple(zip(sources, targets))
            ctx = tuple(sources) + tuple(targets)
            ex = Example(split, cohort, int(seed), ds, i, name, sources[correct], None, pairs, (),
                         None, tuple(targets), correct, None, ctx, cohort, IDENTIFIER_LENGTH,
                         "none", targets[correct], False)
        elif split == "C5":
            sources = take(CANDIDATE_COUNT); answer = take(1)[0]
            edits = 1 + (i % 2)
            targets = [_lexical_neighbor(rng, answer, edits) for _ in range(CANDIDATE_COUNT - 1)] + [answer]
            rng.shuffle(targets)
            correct = targets.index(answer)
            pairs = tuple(zip(sources, targets))
            ctx = tuple(sources) + tuple(targets)
            ex = Example(split, cohort, int(seed), ds, i, name, sources[correct], None, pairs, (),
                         None, tuple(targets), correct, None, ctx, cohort, IDENTIFIER_LENGTH,
                         f"edit{edits}", answer, False)
        elif split == "C3":
            sources = take(CANDIDATE_COUNT); targets = take(CANDIDATE_COUNT); evid = take_ev(CANDIDATE_COUNT)
            correct = rng.randrange(CANDIDATE_COUNT)
            pairs = tuple(zip(sources, targets))
            ctx = tuple(sources) + tuple(targets) + tuple(evid)
            ex = Example(split, cohort, int(seed), ds, i, name, sources[correct], targets[correct],
                         pairs, tuple(evid), None, tuple(evid), correct, evid[correct], ctx,
                         cohort, IDENTIFIER_LENGTH, "none", evid[correct], False)
        else:  # C8 missing-key abstention
            sources = take(CANDIDATE_COUNT); targets = take(CANDIDATE_COUNT); absent = take(1)[0]
            pairs = tuple(zip(sources, targets))
            ctx = tuple(sources) + tuple(targets)  # absent source is NOT in context
            ex = Example(split, cohort, int(seed), ds, i, name, absent, None, pairs, (), None,
                         tuple(targets), None, None, ctx, cohort, IDENTIFIER_LENGTH, "none",
                         ABSTENTION_TOKEN, True)
        out.append(ex.with_hash())
    return out
