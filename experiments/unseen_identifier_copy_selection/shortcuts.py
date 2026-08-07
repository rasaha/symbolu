"""Structure-blind shortcut baselines for the unseen-identifier diagnostic.

Each baseline predicts an answer WITHOUT reading the queried relation. On opaque, randomly-drawn
identifiers every baseline sits at chance in expectation; a baseline that is BOTH practically and
statistically above chance on its relevant split is a leakage signal that must be resolved BEFORE
reserved execution (a hard pre-reserved gate). This module only *computes* the baselines and the
gate decision; the runner enforces the block.

Gate decision (corrective-PR calibration). A baseline blocks only when it clears BOTH legs:
  * practical leg  — point estimate exceeds the practical-equivalence margin: ``p_hat > chance + 0.05``;
  * statistical leg — an EXACT one-sided binomial upper-tail test of H0: p = chance is rejected under
    Holm-Bonferroni family-wise-error control across ALL (split, baseline) comparisons in the gate.
On uniformly-random opaque identifiers (protocol-lock Decision 3) every baseline is at chance, so the
family of finite-sample estimates scatters around chance; the previous flat ``<= chance + 0.05`` rule
compared point estimates to a fixed line with no sampling-error allowance and no multiplicity control,
which false-blocks under the null. The practical 0.05 margin is unchanged; only the decision is now
sampling-aware. A genuine leak (a baseline whose true rate is meaningfully above chance) still yields a
tiny binomial tail and blocks.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from .config import ABSTENTION_TOKEN, CANDIDATE_COUNT
from .tasks import Example

SHORTCUT_BOUND = 0.05  # frozen practical-equivalence margin: the practical leg is chance + 0.05
SHORTCUT_FWER = 0.05   # family-wise error rate for the Holm-Bonferroni multiple-comparison correction

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


# --------------------------------------------------------------------------------------------------
# Statistics: exact one-sided binomial tail + Holm-Bonferroni FWER control (dependency-free).
# --------------------------------------------------------------------------------------------------
def binom_sf_ge(k: int, n: int, p: float) -> float:
    """Exact one-sided upper tail P(X >= k) for X ~ Binomial(n, p), via a stable iterative PMF.

    No SciPy/NumPy dependency and no normal approximation, so the statistical leg is defensible
    independently of any sample size or independence assumption among comparisons."""
    if n <= 0 or k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    ratio = p / (1.0 - p)
    pmf = (1.0 - p) ** n  # P(X = 0)
    tail = 0.0
    for i in range(1, n + 1):
        pmf *= (n - i + 1) / i * ratio  # P(X=i) from P(X=i-1)
        if i >= k:
            tail += pmf
    return min(1.0, tail)


def holm_reject(pvalues: list[float], fwer: float = SHORTCUT_FWER) -> list[bool]:
    """Holm-Bonferroni step-down rejections at family-wise error rate `fwer`.

    Uniformly more powerful than plain Bonferroni and valid without independence assumptions. Returns
    a boolean per input hypothesis (True = rejected = significant)."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    reject = [False] * m
    for rank, idx in enumerate(order):
        threshold = fwer / (m - rank)
        if pvalues[idx] <= threshold:
            reject[idx] = True
        else:
            break  # step-down: once one hypothesis fails, all larger p-values fail too
    return reject


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


def _decide(per_split_counts: dict[str, dict[str, list[int]]], chance: float) -> dict:
    """Apply the dual-condition (practical + Holm-corrected exact-binomial) gate across a whole family.

    `per_split_counts[split][baseline] = [correct, applicable]`. Returns per-split baselines, p-values,
    blocked names, pass flags, and the overall all_pass, plus the family size for transparency."""
    bound = chance + SHORTCUT_BOUND
    # Flatten the family of comparisons; compute exact binomial p-values against the chance null.
    flat: list[tuple[str, str, int, int]] = []
    for split in sorted(per_split_counts):
        for name, (k, n) in per_split_counts[split].items():
            flat.append((split, name, k, n))
    pvalues = [binom_sf_ge(k, n, chance) for (_s, _b, k, n) in flat]
    rejected = holm_reject(pvalues, SHORTCUT_FWER)

    per_split: dict[str, dict] = {}
    all_pass = True
    for i, (split, name, k, n) in enumerate(flat):
        p_hat = (k / n) if n else 0.0
        practical = p_hat > bound
        blocks = bool(practical and rejected[i])
        d = per_split.setdefault(split, {"n": 0, "baselines": {}, "counts": {}, "pvalues": {},
                                         "blocked": [], "competence_floor": bound, "pass": True})
        d["n"] = n
        d["baselines"][name] = p_hat
        d["counts"][name] = [k, n]
        d["pvalues"][name] = pvalues[i]
        if blocks:
            d["blocked"].append(name)
            d["pass"] = False
            all_pass = False
    return {"chance": chance, "bound": bound, "fwer": SHORTCUT_FWER,
            "n_comparisons": len(flat), "per_split": per_split, "all_pass": all_pass}


def shortcut_scores(examples: list[Example]) -> dict:
    """Compute the twelve structure-blind baselines PER SPLIT for ONE seed's cohort and decide the gate.

    Each baseline is scored per split (combining splits would create artificial cross-split frequency,
    so we never do). The block decision is the dual condition documented at module top; the family for
    the Holm correction is all (split, baseline) comparisons in this cohort."""
    chance = 1.0 / CANDIDATE_COUNT
    by_split: dict[str, list[Example]] = {}
    for e in _selection_examples(examples):
        by_split.setdefault(e.split, []).append(e)
    per_split_counts = {split: _baseline_counts_on(sel) for split, sel in by_split.items()}
    return _decide(per_split_counts, chance)


def aggregate_shortcuts(per_seed_scores: list[dict]) -> dict:
    """Aggregate per-seed shortcut results across development seeds (protocol-lock Decision 9).

    Aggregation sums the seed-local integer counts per (split, baseline): pooled score =
    `sum(seed-local correct) / sum(seed-local applicable)`. Frequency state is NEVER recomputed over a
    combined multi-seed pool — only the seed-local counts are summed. The pooled counts then feed the
    same dual-condition gate (exact binomial + Holm) so the multiplicity-aware decision is evaluated on
    the pooled per-split estimates. Per-seed values are preserved descriptively."""
    if not per_seed_scores:
        raise ValueError("aggregate_shortcuts requires at least one per-seed result")
    chance = per_seed_scores[0]["chance"]
    splits = sorted({split for r in per_seed_scores for split in r["per_split"]})
    per_split_counts: dict[str, dict[str, list[int]]] = {}
    per_seed_view: dict[str, dict[str, list[float]]] = {}
    for split in splits:
        summed: dict[str, list[int]] = {}
        view: dict[str, list[float]] = {}
        for result in per_seed_scores:
            entry = result["per_split"].get(split)
            if entry is None:
                continue
            for name, (correct, applicable) in entry["counts"].items():
                acc = summed.setdefault(name, [0, 0])
                acc[0] += correct
                acc[1] += applicable
                view.setdefault(name, []).append(entry["baselines"][name])
        for name, (_correct, applicable) in summed.items():
            if applicable == 0:
                raise ValueError(f"baseline {name!r} on split {split} has zero applicable examples")
        per_split_counts[split] = summed
        per_seed_view[split] = view

    decided = _decide(per_split_counts, chance)
    for split, d in decided["per_split"].items():
        d["per_seed_scores"] = per_seed_view.get(split, {})
    return decided


@dataclass(frozen=True)
class ShortcutStatus:
    passed: bool
    detail: dict


def shortcut_precheck(examples: list[Example]) -> ShortcutStatus:
    result = shortcut_scores(examples)
    return ShortcutStatus(passed=bool(result["all_pass"]), detail=result)
