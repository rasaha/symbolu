"""Common utilities for the Model Selection Policy experiment.

Deterministic-by-construction: all "noise" is a hash of stable keys, so results
are identical across runs and machines without RNG-ordering fragility.

This package is fully self-contained. It imports nothing from the production
tree (Hybrid LLM, ActionGate, TAP, KVPro, Cloud Scaling).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Iterable, List

# ---------------------------------------------------------------------------
# Versions (stamped into every decision record and result artifact)
# ---------------------------------------------------------------------------
REGISTRY_VERSION = "registry_v1"
CORPUS_VERSION = "corpus_v1"
POLICY_VERSION = "policy_v1"
GROUND_TRUTH_VERSION = "ground_truth_v1"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Capability classes used throughout the experiment.
CAPS: List[str] = [
    "reasoning",
    "coding",
    "extraction",
    "summarization",
    "classification",
    "long_context",
    "multilingual",
    "structured_output",
    "tool_use",
]

# Telemetry sample counts per regime (per model x task-class). 0 => cold start.
REGIME_SAMPLES = {"cold": 0, "partial": 6, "mature": 80}
REGIMES = ["cold", "partial", "mature"]


# ---------------------------------------------------------------------------
# Deterministic pseudo-noise
# ---------------------------------------------------------------------------
def _hash_unit(*keys: Any) -> float:
    """Deterministic float in [0, 1) from arbitrary stable keys."""
    s = "|".join(str(k) for k in keys)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(1 << 48)


def det_unit(*keys: Any) -> float:
    """Deterministic value in [0, 1)."""
    return _hash_unit(*keys)


def det_signed(*keys: Any) -> float:
    """Deterministic value in [-1, 1)."""
    return _hash_unit(*keys) * 2.0 - 1.0


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def load_json(name: str) -> Any:
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_registry() -> Dict[str, Any]:
    return load_json("registry_v1.json")


def load_corpus() -> Dict[str, Any]:
    return load_json("corpus_v1.json")


def load_policy() -> Dict[str, Any]:
    return load_json("policy_v1.json")


def load_ground_truth() -> Dict[str, Any]:
    """Ground truth is visible ONLY to the simulator/oracle, never to a routing arm."""
    return load_json("ground_truth_v1.json")


def weighted_caps(cap_vector: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted average of a capability vector over the task's required caps."""
    num = 0.0
    den = 0.0
    for cap, w in weights.items():
        num += w * float(cap_vector.get(cap, 0.0))
        den += w
    return num / den if den else 0.0


def percentile(values: Iterable[float], q: float) -> float:
    xs = sorted(values)
    if not xs:
        return 0.0
    if len(xs) == 1:
        return xs[0]
    idx = q * (len(xs) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(xs) - 1)
    frac = idx - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac
