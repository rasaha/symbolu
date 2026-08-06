"""Structure-blind shortcut baselines for the unseen-identifier diagnostic.

Each baseline predicts an answer WITHOUT reading the queried relation. On opaque, randomly-drawn
identifiers every baseline should sit at chance; a baseline exceeding chance + 0.05 on its relevant
split is a leakage signal that must be resolved BEFORE reserved execution (a hard pre-reserved
gate). This module only *computes* the baselines; the runner enforces the gate.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from .config import ABSTENTION_TOKEN, CANDIDATE_COUNT
from .tasks import Example

SHORTCUT_BOUND = 0.05  # frozen: threshold is chance + 0.05

# The frozen twelve structure-blind baselines (protocol-lock Decision 9; completed here to 12).
BASELINE_NAMES: tuple[str, ...] = (
    "first_target",
    "last_target",
    "middle_target",
    "most_frequent_target",
    "lexical_similarity",
    "prefix_match",
    "character_overlap",
    "constant_abstention",
    # the four completed here (protocol-lock Decision 8), each mechanical from existing metadata:
    "source_target_cooccurrence",
    "seen_id_frequency",
    "output_template_leakage",
    "task_label_leakage",
)

# The frozen output contract places the answer at no fixed candidate position; index 0 is the
# frozen probe position for the output-template-leakage baseline (verifies the template leaks nothing).
FROZEN_OUTPUT_POSITION: int = 0


def _char_overlap(a: str, b: str) -> int:
    return len(set(a) & set(b))


def _prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _frozen_label_index(task_name: str, k: int) -> int:
    """Deterministic frozen map from a task label to a candidate slot (salt-free sha256)."""
    digest = hashlib.sha256(task_name.encode("ascii")).hexdigest()
    return int(digest, 16) % k


def _selection_examples(examples: list[Example]) -> list[Example]:
    return [e for e in examples if e.correct_position is not None and not e.expected_abstention]


def _targets(e: Example) -> list[str]:
    return [t for _, t in e.pairs]


def _pickers(sel: list[Example]) -> dict:
    """Frozen candidate-picking rules for every baseline EXCEPT constant_abstention.

    Every frequency-based picker derives its state ONLY from `sel` (one seed, one split); it is never
    recomputed over a combined multi-seed pool. Deterministic lexicographic tie-breaks throughout."""
    freq = Counter(t for e in sel for t in _targets(e))
    cooc = Counter((e.query_source, t) for e in sel for t in _targets(e))
    id_freq = Counter(identifier for e in sel for identifier in e.context_ids)

    def cooccurrence(e: Example) -> str:
        # highest (query_source, target) co-occurrence count; tie-break smallest identifier.
        return min(_targets(e), key=lambda t: (-cooc[(e.query_source, t)], t))

    def seen_frequency(e: Example) -> str:
        return min(_targets(e), key=lambda t: (-id_freq[t], t))

    def output_template(e: Example) -> str:
        return _targets(e)[FROZEN_OUTPUT_POSITION]

    def task_label(e: Example) -> str:
        targets = _targets(e)
        return targets[_frozen_label_index(e.task_name, len(targets))]

    return {
        "first_target": lambda e: _targets(e)[0],
        "last_target": lambda e: _targets(e)[-1],
        "middle_target": lambda e: _targets(e)[CANDIDATE_COUNT // 2],
        "most_frequent_target": lambda e: max(_targets(e), key=lambda t: freq[t]),
        "lexical_similarity": lambda e: max(_targets(e), key=lambda t: (_char_overlap(t, e.query_source or ""), t)),
        "prefix_match": lambda e: max(_targets(e), key=lambda t: (_prefix_len(t, e.query_source or ""), t)),
        "character_overlap": lambda e: max(_targets(e), key=lambda t: (_char_overlap(t, e.query_source or ""), t)),
        "source_target_cooccurrence": cooccurrence,
        "seen_id_frequency": seen_frequency,
        "output_template_leakage": output_template,
        "task_label_leakage": task_label,
    }


def _baseline_counts_on(sel: list[Example]) -> dict[str, list[int]]:
    """Per-baseline [correct_count, applicable_count] within ONE seed/split cohort.

    A picker that returns no prediction for an applicable example is an implementation defect (it
    would raise), never a silently-omitted example."""
    pickers = _pickers(sel)
    counts: dict[str, list[int]] = {}
    for name, pick in pickers.items():
        correct = sum(1 for e in sel if pick(e) == e.expected_output)
        counts[name] = [correct, len(sel)]
    counts["constant_abstention"] = [
        sum(1 for e in sel if ABSTENTION_TOKEN == e.expected_output), len(sel)
    ]
    return counts


def _baselines_on(sel: list[Example]) -> dict[str, float]:
    """The twelve baseline scores within ONE seed/split cohort (kept as means for readability)."""
    n = len(sel)
    counts = _baseline_counts_on(sel)
    return {name: (correct / n if n else 0.0) for name, (correct, _n) in counts.items()}


def shortcut_scores(examples: list[Example]) -> dict:
    """Compute the twelve structure-blind baselines PER SPLIT for ONE seed's cohort.

    Returns per-split baselines (means), per-split [correct, applicable] counts, and an overall pass
    flag. Each baseline must be <= chance + 0.05 on its own split; combining splits would create
    artificial cross-split frequency, so we never do. Threshold equality passes (`<=`)."""
    chance = 1.0 / CANDIDATE_COUNT
    by_split: dict[str, list[Example]] = {}
    for e in _selection_examples(examples):
        by_split.setdefault(e.split, []).append(e)
    per_split: dict[str, dict] = {}
    all_pass = True
    for split, sel in sorted(by_split.items()):
        baselines = _baselines_on(sel)
        counts = _baseline_counts_on(sel)
        split_pass = all(v <= chance + SHORTCUT_BOUND for v in baselines.values())
        all_pass = all_pass and split_pass
        per_split[split] = {"n": len(sel), "baselines": baselines, "counts": counts,
                            "competence_floor": chance + SHORTCUT_BOUND, "pass": split_pass}
    return {"chance": chance, "bound": chance + SHORTCUT_BOUND, "per_split": per_split,
            "all_pass": all_pass}


def aggregate_shortcuts(per_seed_scores: list[dict]) -> dict:
    """Aggregate per-seed shortcut results across development seeds (protocol-lock Decision 9).

    Aggregation is an example-count-weighted mean of seed-local scores:
    `sum(seed-local correct) / sum(seed-local applicable)` per (split, baseline). Frequency state is
    NEVER recomputed over a combined multi-seed pool — only the seed-local counts are summed here.
    Threshold equality passes; per-seed values are preserved descriptively; any applicable split
    whose aggregate exceeds its competence floor blocks execution (`all_pass=False`)."""
    if not per_seed_scores:
        raise ValueError("aggregate_shortcuts requires at least one per-seed result")
    chance = per_seed_scores[0]["chance"]
    floor = chance + SHORTCUT_BOUND
    # collect the set of splits present across seeds
    splits = sorted({split for r in per_seed_scores for split in r["per_split"]})
    per_split: dict[str, dict] = {}
    all_pass = True
    for split in splits:
        summed: dict[str, list[int]] = {}
        per_seed_scores_view: dict[str, list[float]] = {}
        for result in per_seed_scores:
            entry = result["per_split"].get(split)
            if entry is None:
                continue
            for name, (correct, applicable) in entry["counts"].items():
                acc = summed.setdefault(name, [0, 0])
                acc[0] += correct
                acc[1] += applicable
                per_seed_scores_view.setdefault(name, []).append(
                    entry["baselines"][name]
                )
        baselines: dict[str, float] = {}
        passes: dict[str, bool] = {}
        for name, (correct, applicable) in summed.items():
            if applicable == 0:
                raise ValueError(f"baseline {name!r} on split {split} has zero applicable examples")
            score = correct / applicable
            baselines[name] = score
            passes[name] = score <= floor
        split_pass = all(passes.values())
        all_pass = all_pass and split_pass
        per_split[split] = {
            "counts": summed,
            "baselines": baselines,
            "per_seed_scores": per_seed_scores_view,
            "competence_floor": floor,
            "pass": split_pass,
        }
    return {"chance": chance, "bound": floor, "per_split": per_split, "all_pass": all_pass}


@dataclass(frozen=True)
class ShortcutStatus:
    passed: bool
    detail: dict


def shortcut_precheck(examples: list[Example]) -> ShortcutStatus:
    result = shortcut_scores(examples)
    return ShortcutStatus(passed=bool(result["all_pass"]), detail=result)
