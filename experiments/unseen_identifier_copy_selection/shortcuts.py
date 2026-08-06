"""Structure-blind shortcut baselines for the unseen-identifier diagnostic.

Each baseline predicts an answer WITHOUT reading the queried relation. On opaque, randomly-drawn
identifiers every baseline should sit at chance; a baseline exceeding chance + 0.05 on its relevant
split is a leakage signal that must be resolved BEFORE reserved execution (a hard pre-reserved
gate). This module only *computes* the baselines; the runner enforces the gate.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .config import ABSTENTION_TOKEN, CANDIDATE_COUNT
from .tasks import Example

SHORTCUT_BOUND = 0.05  # frozen: threshold is chance + 0.05


def _char_overlap(a: str, b: str) -> int:
    return len(set(a) & set(b))


def _prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _selection_examples(examples: list[Example]) -> list[Example]:
    return [e for e in examples if e.correct_position is not None and not e.expected_abstention]


def _targets(e: Example) -> list[str]:
    return [t for _, t in e.pairs]


def _baselines_on(sel: list[Example]) -> dict[str, float]:
    n = len(sel)
    freq = Counter(t for e in sel for t in _targets(e))

    def acc(pick) -> float:
        return sum(1 for e in sel if pick(e) == e.expected_output) / n

    return {
        "first_target": acc(lambda e: _targets(e)[0]),
        "last_target": acc(lambda e: _targets(e)[-1]),
        "middle_target": acc(lambda e: _targets(e)[CANDIDATE_COUNT // 2]),
        "most_frequent_target": acc(lambda e: max(_targets(e), key=lambda t: freq[t])),
        "lexical_similarity": acc(lambda e: max(_targets(e), key=lambda t: (_char_overlap(t, e.query_source or ""), t))),
        "prefix_match": acc(lambda e: max(_targets(e), key=lambda t: (_prefix_len(t, e.query_source or ""), t))),
        "character_overlap": acc(lambda e: max(_targets(e), key=lambda t: (_char_overlap(t, e.query_source or ""), t))),
        "constant_abstention": sum(1 for e in sel if ABSTENTION_TOKEN == e.expected_output) / n,
    }


def shortcut_scores(examples: list[Example]) -> dict:
    """Compute structure-blind baselines PER SPLIT (protocol: each on its relevant split).

    Returns per-split baselines plus an overall pass flag. Each baseline must be <= chance + 0.05 on
    its own split; combining splits would create artificial cross-split frequency, so we never do."""
    chance = 1.0 / CANDIDATE_COUNT
    by_split: dict[str, list[Example]] = {}
    for e in _selection_examples(examples):
        by_split.setdefault(e.split, []).append(e)
    per_split: dict[str, dict] = {}
    all_pass = True
    for split, sel in sorted(by_split.items()):
        baselines = _baselines_on(sel)
        split_pass = all(v <= chance + SHORTCUT_BOUND for v in baselines.values())
        all_pass = all_pass and split_pass
        per_split[split] = {"n": len(sel), "baselines": baselines, "pass": split_pass}
    return {"chance": chance, "bound": chance + SHORTCUT_BOUND, "per_split": per_split,
            "all_pass": all_pass}


@dataclass(frozen=True)
class ShortcutStatus:
    passed: bool
    detail: dict


def shortcut_precheck(examples: list[Example]) -> ShortcutStatus:
    result = shortcut_scores(examples)
    return ShortcutStatus(passed=bool(result["all_pass"]), detail=result)
