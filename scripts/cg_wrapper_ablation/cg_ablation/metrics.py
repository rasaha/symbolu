"""Objective metrics + statistics for the CG-wrapper ablation.

Everything here is pure Python / math (numpy optional) so it runs on CPU with no torch and no
GPU. Logit-level metrics accept plain nested lists or numpy arrays so tests can exercise them
without a real model.

No subjective "coherence" score lives here by design — only objective, reproducible measures.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Answer extraction + exact match (GSM8K-style)
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_HASH_ANSWER_RE = re.compile(r"####\s*(-?\d[\d,]*(?:\.\d+)?)")


def extract_final_integer(text: str) -> Optional[int]:
    """Extract the final integer answer from a free-form response.

    Prefers an explicit ``#### N`` marker (GSM8K convention); otherwise takes the last number
    in the text. Returns ``None`` if no number is present. Floats with integer value (``42.0``)
    are accepted; genuinely fractional answers return ``None`` (the eval set is integer-valued).
    """
    if text is None:
        return None
    m = _HASH_ANSWER_RE.findall(text)
    candidates = m if m else _NUMBER_RE.findall(text)
    if not candidates:
        return None
    raw = candidates[-1].replace(",", "")
    try:
        val = float(raw)
    except ValueError:
        return None
    if abs(val - round(val)) > 1e-9:
        return None
    return int(round(val))


def exact_match(prediction: str, gold: int) -> bool:
    """True iff the final integer extracted from ``prediction`` equals ``gold``."""
    return extract_final_integer(prediction) == gold


# ---------------------------------------------------------------------------
# JSON validity / format adherence
# ---------------------------------------------------------------------------

def _extract_json_blob(text: str) -> Optional[str]:
    """Return the first balanced ``{...}`` substring, or None. Tolerates surrounding prose."""
    if text is None:
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


def json_parse_ok(text: str) -> bool:
    """True iff a balanced JSON object can be extracted from ``text`` and parses."""
    blob = _extract_json_blob(text)
    if blob is None:
        return False
    try:
        json.loads(blob)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def json_has_keys(text: str, required_keys: Sequence[str]) -> bool:
    """True iff ``text`` contains a parseable JSON object that has all ``required_keys``."""
    blob = _extract_json_blob(text)
    if blob is None:
        return False
    try:
        obj = json.loads(blob)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(obj, dict):
        return False
    return all(k in obj for k in required_keys)


# ---------------------------------------------------------------------------
# Instruction-following / format constraints
# ---------------------------------------------------------------------------

def constraint_satisfied(text: str, constraint: Dict[str, Any]) -> bool:
    """Evaluate a single declarative format constraint against a response.

    Supported constraint ``type`` values (all objective, deterministic):
      - ``max_words``  {"type":"max_words","value":N}
      - ``exact_words``{"type":"exact_words","value":N}
      - ``ends_with``  {"type":"ends_with","value":"DONE"}
      - ``starts_with``{"type":"starts_with","value":"Answer:"}
      - ``contains``   {"type":"contains","value":"foo"}
      - ``not_contains`` {"type":"not_contains","value":"foo"}
      - ``line_count`` {"type":"line_count","value":N}
      - ``regex``      {"type":"regex","value":"^[A-Z].*$"}
      - ``one_of``     {"type":"one_of","value":["yes","no"]}  (case-insensitive, trimmed)
    Unknown types return False (fail closed).
    """
    if text is None:
        return False
    t = constraint.get("type")
    v = constraint.get("value")
    s = text.strip()
    if t == "max_words":
        return len(s.split()) <= int(v)
    if t == "exact_words":
        return len(s.split()) == int(v)
    if t == "ends_with":
        return s.endswith(str(v))
    if t == "starts_with":
        return s.startswith(str(v))
    if t == "contains":
        return str(v) in text
    if t == "not_contains":
        return str(v) not in text
    if t == "line_count":
        return len([ln for ln in s.splitlines() if ln.strip()]) == int(v)
    if t == "regex":
        return re.search(str(v), text) is not None
    if t == "one_of":
        return s.lower() in {str(x).lower() for x in v}
    return False


# ---------------------------------------------------------------------------
# Cross-seed answer consistency
# ---------------------------------------------------------------------------

def pairwise_agreement(answers: Sequence[Any]) -> float:
    """Mean pairwise agreement over a list of per-seed answers for one example.

    Returns the fraction of unordered seed-pairs whose answers are equal. With <2 answers,
    returns 1.0 (degenerate, fully consistent). ``None`` answers compare unequal to everything
    except another ``None``.
    """
    n = len(answers)
    if n < 2:
        return 1.0
    agree = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1
            if answers[i] == answers[j]:
                agree += 1
    return agree / total if total else 1.0


# ---------------------------------------------------------------------------
# Paired statistics: bootstrap CI + McNemar
# ---------------------------------------------------------------------------

def paired_bootstrap_ci(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 12345,
) -> Tuple[float, float, float]:
    """Paired bootstrap CI for the mean difference ``mean(b) - mean(a)``.

    Returns ``(point_estimate, lo, hi)`` for the ``(1-alpha)`` interval. ``a`` and ``b`` are
    paired per-example scores (same length). Pure-Python RNG (no numpy required) for portability.
    """
    if len(a) != len(b):
        raise ValueError("paired_bootstrap_ci requires equal-length paired samples")
    n = len(a)
    diffs = [float(b[i]) - float(a[i]) for i in range(n)]
    point = sum(diffs) / n if n else 0.0
    if n == 0:
        return 0.0, 0.0, 0.0
    import random

    rng = random.Random(seed)
    means: List[float] = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return point, lo, hi


def _binom_two_sided_p(b: int, c: int) -> float:
    """Exact two-sided binomial p-value for McNemar with discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # two-sided exact: 2 * P(X <= k) under Binom(n, 0.5), capped at 1.0
    cum = 0.0
    for i in range(0, k + 1):
        cum += math.comb(n, i)
    p = 2.0 * cum / (2 ** n)
    return min(1.0, p)


def mcnemar_exact(a: Sequence[bool], b: Sequence[bool]) -> Dict[str, Any]:
    """Exact (binomial) McNemar test for paired binary outcomes ``a`` vs ``b``.

    ``a``/``b`` are per-example pass/fail (e.g. exact-match) for two arms. Returns a dict with
    discordant counts ``b01`` (a wrong, b right), ``b10`` (a right, b wrong), the exact two-sided
    p-value, and the net ``delta = mean(b) - mean(a)``.
    """
    if len(a) != len(b):
        raise ValueError("mcnemar_exact requires equal-length paired samples")
    b01 = sum(1 for x, y in zip(a, b) if (not x) and y)   # a wrong -> b right (b improves)
    b10 = sum(1 for x, y in zip(a, b) if x and (not y))   # a right -> b wrong (b regresses)
    p = _binom_two_sided_p(b01, b10)
    n = len(a)
    delta = (sum(1 for y in b if y) - sum(1 for x in a if x)) / n if n else 0.0
    return {"b01_improve": b01, "b10_regress": b10, "p_value": p, "delta": delta, "n": n}


# ---------------------------------------------------------------------------
# Logit-level diagnostics (base vs wrapper)
# ---------------------------------------------------------------------------

def _softmax_row(logits: Sequence[float]) -> List[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    z = sum(exps)
    return [e / z for e in exps]


def logit_kl_per_token(
    base_logits: Sequence[Sequence[float]],
    wrapper_logits: Sequence[Sequence[float]],
) -> float:
    """Mean per-token KL( softmax(base) || softmax(wrapper) ) in nats.

    Inputs are ``[T, V]`` nested sequences (one row of vocab logits per token position). Uses
    base as P and wrapper as Q, matching the plan's ``KL(base || wrapper)``.
    """
    if len(base_logits) != len(wrapper_logits):
        raise ValueError("base and wrapper must have the same number of token positions")
    if not base_logits:
        return 0.0
    total = 0.0
    for pb, pw in zip(base_logits, wrapper_logits):
        P = _softmax_row(pb)
        Q = _softmax_row(pw)
        kl = 0.0
        for p, q in zip(P, Q):
            if p > 0.0:
                kl += p * math.log(p / max(q, 1e-12))
        total += kl
    return total / len(base_logits)


def top1_flip_rate(
    base_logits: Sequence[Sequence[float]],
    wrapper_logits: Sequence[Sequence[float]],
) -> float:
    """Fraction of token positions where argmax(base) != argmax(wrapper)."""
    if len(base_logits) != len(wrapper_logits):
        raise ValueError("base and wrapper must have the same number of token positions")
    if not base_logits:
        return 0.0
    flips = 0
    for pb, pw in zip(base_logits, wrapper_logits):
        if _argmax(pb) != _argmax(pw):
            flips += 1
    return flips / len(base_logits)


def _argmax(seq: Sequence[float]) -> int:
    best_i, best_v = 0, seq[0]
    for i, v in enumerate(seq):
        if v > best_v:
            best_i, best_v = i, v
    return best_i


# ---------------------------------------------------------------------------
# Aggregation helper
# ---------------------------------------------------------------------------

def summarize_rate(values: Sequence[bool]) -> Dict[str, float]:
    """Return {n, k, rate} for a list of booleans."""
    n = len(values)
    k = sum(1 for v in values if v)
    return {"n": n, "k": k, "rate": (k / n) if n else 0.0}
