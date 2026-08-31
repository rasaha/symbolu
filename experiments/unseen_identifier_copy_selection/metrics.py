"""Pure deterministic metric functions for the unseen-identifier diagnostic.

Inputs are lists of (Example, ParseResult); every function is a pure aggregation with no I/O and no
randomness. Verdicts are never inferred here (see verdict.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import IDENTIFIER_LENGTH
from .parser import OutputCategory, ParseResult
from .tasks import Example

Pair = tuple[Example, ParseResult]


def _safe(n: int, d: int) -> float:
    return 0.0 if d == 0 else n / d


def exact_accuracy(pairs: list[Pair]) -> float:
    ans = [p for p in pairs if not p[0].expected_abstention]
    return _safe(sum(1 for e, r in ans if r.category is OutputCategory.EXACT_CORRECT), len(ans))


def token_accuracy(pairs: list[Pair]) -> float:
    ans = [p for p in pairs if not p[0].expected_abstention]
    total = correct = 0
    for e, r in ans:
        gold = e.expected_output
        got = r.normalized
        for i in range(IDENTIFIER_LENGTH):
            total += 1
            if i < len(got) and got[i] == gold[i]:
                correct += 1
    return _safe(correct, total)


def malformed_rate(pairs: list[Pair]) -> float:
    ans = [p for p in pairs if not p[0].expected_abstention]
    return _safe(sum(1 for e, r in ans if r.category is OutputCategory.MALFORMED), len(ans))


def wrong_in_context_rate(pairs: list[Pair]) -> float:
    ans = [p for p in pairs if not p[0].expected_abstention]
    return _safe(sum(1 for e, r in ans if r.category is OutputCategory.WRONG_IN_CONTEXT), len(ans))


def fabricated_rate(pairs: list[Pair]) -> float:
    """Out-of-context fabricated identifiers over ALL examples (answer-expected + abstention)."""
    n = fab = 0
    for e, r in pairs:
        n += 1
        if r.category is OutputCategory.FABRICATED_OUT_OF_CONTEXT:
            fab += 1
    return _safe(fab, n)


def abstention_accuracy(pairs: list[Pair]) -> float:
    abst = [p for p in pairs if p[0].expected_abstention]
    return _safe(sum(1 for e, r in abst if r.category is OutputCategory.CORRECT_ABSTENTION), len(abst))


def false_answer_rate(pairs: list[Pair]) -> float:
    """Fraction of abstention-expected examples where the model answered instead of abstaining."""
    abst = [p for p in pairs if p[0].expected_abstention]
    answered = sum(
        1 for e, r in abst
        if r.category in (OutputCategory.WRONG_IN_CONTEXT, OutputCategory.FABRICATED_OUT_OF_CONTEXT,
                          OutputCategory.EXACT_CORRECT, OutputCategory.TOKEN_PARTIAL)
    )
    return _safe(answered, len(abst))


def position_accuracy(pairs: list[Pair]) -> dict[str, float]:
    order = ("first", "middle", "last")
    out: dict[str, float] = {}
    for idx, name in enumerate(order):
        grp = [(e, r) for e, r in pairs
               if e.correct_position is not None and e.correct_position % 3 == idx
               and not e.expected_abstention]
        out[name] = _safe(sum(1 for e, r in grp if r.category is OutputCategory.EXACT_CORRECT), len(grp))
    return out


def position_spread(pairs: list[Pair]) -> float:
    acc = position_accuracy(pairs)
    vals = [v for v in acc.values()]
    return (max(vals) - min(vals)) if vals else 0.0


def lexical_degradation(decoy_pairs: list[Pair], clean_pairs: list[Pair]) -> float:
    return exact_accuracy(clean_pairs) - exact_accuracy(decoy_pairs)


def seen_unseen_gap(seen_pairs: list[Pair], unseen_pairs: list[Pair]) -> float:
    return exact_accuracy(seen_pairs) - exact_accuracy(unseen_pairs)


@dataclass(frozen=True)
class SplitMetrics:
    split: str
    n: int
    exact: float
    token: float
    malformed: float
    wrong_in_context: float
    fabricated: float
    abstention: float
    false_answer: float
    position_spread: float


def split_metrics(split: str, pairs: list[Pair]) -> SplitMetrics:
    return SplitMetrics(
        split=split, n=len(pairs), exact=exact_accuracy(pairs), token=token_accuracy(pairs),
        malformed=malformed_rate(pairs), wrong_in_context=wrong_in_context_rate(pairs),
        fabricated=fabricated_rate(pairs), abstention=abstention_accuracy(pairs),
        false_answer=false_answer_rate(pairs), position_spread=position_spread(pairs),
    )


def replication_count(per_seed_pass: list[bool]) -> int:
    """Number of seeds meeting a gate (e.g. for the '>= 4 of 5' rule)."""
    return sum(1 for x in per_seed_pass if x)
