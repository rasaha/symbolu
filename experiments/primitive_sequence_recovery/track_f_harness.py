"""Track F harness — varṇa boundary INFERENCE-STEERING mechanics (synthetic judge scores only).

Proves the Track F scoring/decision mechanics: per-arm judge means (X/A/B/F/I/[R]), the inference
deltas (A_vs_X magnitude; A distinct from B/I/F via pairwise distances), correctness preservation,
usefulness gain, and poetic-noise / hallucination gates — on SYNTHETIC judge scores handed *in*.
No LLM, no network, no real data. It computes nothing about varṇa truth; it labels behavior deltas.

Guardrails: loads ONLY fixtures marked toy_not_for_scoring=true AND synthetic_only=true; rejects
real Sanskrit/varṇa/root markers, forbidden labels, malformed cases, and incomplete scorer output.
Emits only the allowed Track F labels; never ONTOLOGICAL_SIGNAL / SANSKRIT_PRIVILEGE / a Track E
BOUNDARY label. Track B remains BLOCKED. See TRACK_F_* docs.
"""
from __future__ import annotations

import json
import pathlib
import random
from statistics import mean

ARMS_REQUIRED = ("X", "A", "B", "F", "I")     # normal, real, scrambled, dict/etym, Barnum
OPTIONAL_ARMS = ("R",)                          # random unrelated boundary (optional)
ARM_DIMS = ("correctness", "usefulness", "poetic_noise", "hallucination")
A_DIST_KEYS = ("to_X", "to_B", "to_F", "to_I")   # how different A's output is from each arm [0,1]

ALLOWED_LABELS = ("INFERENCE_STEERING_SIGNAL", "PROMPT_PRIMING_ONLY", "SCRAMBLE_EQUIVALENT",
                  "BARNUM_EQUIVALENT", "CORRECTNESS_DEGRADED", "NO_EFFECT", "INCONCLUSIVE")
FORBIDDEN_LABELS = ("ONTOLOGICAL_SIGNAL", "EXPERIENTIAL_WEATHER_SIGNAL", "SANSKRIT_PRIVILEGE",
                    "BOUNDARY_CONSTRAINT_SIGNAL", "BOUNDARY_ONTOLOGICAL")
BANNED_REAL = ("sanskrit", "varṇa", "varna", "vṛtti", "vritti", "devanagari", "iast", "dhātu",
               "dhatu")

EPS = 0.05          # separability band on the [0,1] judge scale
NOISE_THRESH = 0.5  # A's poetic-noise ceiling for a clean signal
HALLUC_THRESH = 0.3  # A's hallucination ceiling before correctness is deemed degraded


class RejectedFixture(ValueError):
    """Raised (loudly) for any invalid/contaminated/malformed toy fixture."""


# ------------------------------------------------------------------ loading ---------
def load_cases(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if data.get("toy_not_for_scoring") is not True or data.get("synthetic_only") is not True:
        raise RejectedFixture("top-level toy flags missing/false (toy_not_for_scoring + synthetic_only)")
    return data["cases"]


# --------------------------------------------------------------- validation --------
def _scan_forbidden(case):
    blob = json.dumps(case, ensure_ascii=False).lower()
    for t in BANNED_REAL:
        if t in blob:
            raise RejectedFixture(f"real-language marker present: {t!r}")
    for lab in FORBIDDEN_LABELS:
        if lab.lower() in blob:
            raise RejectedFixture(f"forbidden label present: {lab}")


def _num01(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= v <= 1.0


def validate_case(case):
    if case.get("toy_not_for_scoring") is not True or case.get("synthetic_only") is not True:
        raise RejectedFixture("per-case toy flags missing/false")
    if case.get("contamination") is True:
        raise RejectedFixture("contamination marker set")
    _scan_forbidden(case)
    items = case.get("items")
    if not items:
        raise RejectedFixture("no items")
    for it in items:
        arms = it.get("arms", {})
        for a in ARMS_REQUIRED:
            if a not in arms:
                raise RejectedFixture(f"missing arm {a}")
            for d in ARM_DIMS:
                if not _num01(arms[a].get(d)):
                    raise RejectedFixture(f"arm {a} dim {d} missing/invalid")
        dist = it.get("a_distances", {})
        for k in A_DIST_KEYS:
            if not _num01(dist.get(k)):
                raise RejectedFixture(f"a_distances {k} missing/invalid")


# --------------------------------------------------------------- metrics -----------
def compute_metrics(items):
    def am(arm, dim):
        return mean(it["arms"][arm][dim] for it in items)
    def dm(key):
        return mean(it["a_distances"][key] for it in items)
    correctness_preserved = am("A", "correctness") - am("X", "correctness")
    usefulness_gain = am("A", "usefulness") - max(am("X", "usefulness"),
                                                  am("B", "usefulness"), am("I", "usefulness"))
    return {
        "delta_A_vs_X": dm("to_X"),        # magnitude of A's change vs normal (necessary)
        "spec_A_vs_B": dm("to_B"),         # A distinct from scrambled
        "spec_A_vs_I": dm("to_I"),         # A distinct from Barnum
        "incr_A_vs_F": dm("to_F"),         # A distinct from dictionary/etymology
        "correctness_preserved": correctness_preserved,
        "usefulness_gain": usefulness_gain,
        "noise_A": am("A", "poetic_noise"),
        "halluc_A": am("A", "hallucination"),
    }


# --------------------------------------------------------------- decision ----------
def decide(m, eps=EPS):
    if m["delta_A_vs_X"] <= eps:                                   # A does not change output
        return "NO_EFFECT"
    if m["correctness_preserved"] < -eps or m["halluc_A"] > HALLUC_THRESH:
        return "CORRECTNESS_DEGRADED"                              # harmful steering
    low_B = m["spec_A_vs_B"] <= eps
    low_I = m["spec_A_vs_I"] <= eps
    if low_B and low_I:                                            # any boundary steers the same way
        return "PROMPT_PRIMING_ONLY"
    if low_B:                                                      # scrambled steers like real
        return "SCRAMBLE_EQUIVALENT"
    if low_I:                                                      # generic Barnum steers like real
        return "BARNUM_EQUIVALENT"
    if m["usefulness_gain"] <= eps or m["noise_A"] > NOISE_THRESH:  # steers distinctly but uselessly
        return "PROMPT_PRIMING_ONLY"
    if all(m[k] > eps for k in ("delta_A_vs_X", "spec_A_vs_B", "spec_A_vs_I",
                                "incr_A_vs_F", "usefulness_gain")):
        return "INFERENCE_STEERING_SIGNAL"
    return "INCONCLUSIVE"


def process_case(case, eps=EPS):
    validate_case(case)
    metrics = compute_metrics(case["items"])
    label = decide(metrics, eps)
    assert label in ALLOWED_LABELS and label not in FORBIDDEN_LABELS, label
    return {"case_id": case.get("case_id"), "task_type": case.get("task_type"), "label": label,
            "metrics": {k: round(v, 4) for k, v in metrics.items()}}


# ------------------------------------------------ blinding utility (demonstration) --
def build_judge_packet(item, seed=0):
    """Anonymize per-arm outputs into resp_* + hide arm identities into a judge packet + key.
    Demonstrates the arm-blinding a real judge pass would apply. Not used by the metric path."""
    rng = random.Random(seed)
    arms = [a for a in ARMS_REQUIRED + OPTIONAL_ARMS if a in item["arms"]]
    rng.shuffle(arms)
    key, packet = {}, {"outputs": []}
    for i, a in enumerate(arms, 1):
        aid = f"resp_{i}"
        key[aid] = a
        packet["outputs"].append({"anon_id": aid})   # text would be attached in a real run
    return packet, key


def run_real_pilot(*a, **k):
    raise NotImplementedError("Real Track F requires explicit approval + a frozen config + a "
                              "judge; not implemented. Synthetic mechanics only.")
