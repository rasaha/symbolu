"""Shared utilities for the real-model shadow pilot.

Deterministic-by-construction. Imports nothing from the production tree.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Iterable, List

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PKG_DIR, "data")
RESULTS_DIR = os.path.join(PKG_DIR, "results")

REGISTRY_VERSION = "pilot_registry_v1"
CORPUS_VERSION = "pilot_corpus_v1"
POLICY_VERSION = "pilot_policy_v1"

TASK_CLASSES = [
    "structured_extraction",
    "classification",
    "summarization",
    "long_document_qa",
    "grounded_comparison",
    "clause_identification",
    "schema_constrained_generation",
]

REGIMES = ["cold", "partial", "mature"]


def _hash_unit(*keys: Any) -> float:
    s = "|".join(str(k) for k in keys)
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16) / float(1 << 48)


def det_unit(*keys: Any) -> float:
    return _hash_unit(*keys)


def det_signed(*keys: Any) -> float:
    return _hash_unit(*keys) * 2.0 - 1.0


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def percentile(values: Iterable[float], q: float) -> float:
    xs = sorted(values)
    if not xs:
        return 0.0
    if len(xs) == 1:
        return xs[0]
    idx = q * (len(xs) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] * (1 - (idx - lo)) + xs[hi] * (idx - lo)


def approx_tokens(text: str) -> int:
    """Cheap deterministic token estimate (~4 chars/token) for cost/context math."""
    return max(1, len(text) // 4)
