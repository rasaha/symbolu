"""Track E synthetic harness — varṇa boundary-constraint MECHANICS (toy data only).

Proves the Track E scoring/decision mechanics: per-arm MRR/Top-1/pairwise, the incremental
deltas (A_vs_X primary, plus A_vs_B/F/D/I), and the decision labels — on SYNTHETIC toy inputs.
No LLM, no network, no real data. Accepts a synthetic scorer's per-arm candidate scores *in*;
computes nothing about the hypothesis. Real Track E is not runnable from here.

Guardrails: loads ONLY fixtures marked toy_not_for_scoring=true AND synthetic_only=true; rejects
real Sanskrit/varṇa/vṛtti markers, forbidden labels, malformed candidate sets, and incomplete
scorer output. Emits only the allowed Track E labels; never EXPERIENTIAL_WEATHER_SIGNAL /
ONTOLOGICAL_SIGNAL / SANSKRIT_PRIVILEGE. Track B remains BLOCKED. See TRACK_E_* docs.
"""
from __future__ import annotations

import json
import pathlib
import random
from statistics import mean

ARMS_REQUIRED = ("A", "B", "X", "F", "D", "I")   # real, scrambled, context, etym, dict, Barnum
ALLOWED_LABELS = ("BOUNDARY_CONSTRAINT_SIGNAL", "NO_SIGNAL", "CONTEXT_ONLY_EXPLAINS",
                  "ETYMOLOGY_EXPLAINS", "SCRAMBLE_EQUIVALENT", "BARNUM_BOUNDARY", "INCONCLUSIVE")
FORBIDDEN_LABELS = ("BOUNDARY_ONTOLOGICAL", "ONTOLOGICAL_SIGNAL", "EXPERIENTIAL_WEATHER_SIGNAL",
                    "SANSKRIT_PRIVILEGE")
BANNED_REAL = ("sanskrit", "varṇa", "varna", "vṛtti", "vritti", "devanagari", "iast", "dhātu",
               "dhatu")
EPS = 0.02   # equivalence band for "beats" / "ties"


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
        cands = it.get("candidates", [])
        cids = [c.get("candidate_id") for c in cands]
        if len(cids) < 3:
            raise RejectedFixture("malformed candidate set: <3 candidates")
        if len(set(cids)) != len(cids):
            raise RejectedFixture("malformed candidate set: duplicate candidate_id")
        roles = [c.get("role") for c in cands]
        if roles.count("context_correct") != 1:
            raise RejectedFixture("malformed candidate set: need exactly one context_correct")
        correct = it.get("context_correct")
        if correct not in cids:
            raise RejectedFixture("context_correct id not among candidates")
        sc = it.get("arm_scores", {})
        for a in ARMS_REQUIRED:
            if a not in sc:
                raise RejectedFixture(f"scorer output missing arm {a}")
            for cid in cids:
                v = sc[a].get(cid)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0.0 <= v <= 1.0):
                    raise RejectedFixture(f"scorer output missing/invalid score {a}/{cid}")


# --------------------------------------------------------------- metrics -----------
def _rank(scores, correct, cids):
    return sorted(cids, key=lambda c: (-scores[c], c)).index(correct) + 1


def arm_metrics(items):
    agg = {a: {"rr": [], "top1": [], "pw": []} for a in ARMS_REQUIRED}
    for it in items:
        cids = [c["candidate_id"] for c in it["candidates"]]
        correct = it["context_correct"]
        negs = [c for c in cids if c != correct]
        for a in ARMS_REQUIRED:
            sc = it["arm_scores"][a]
            r = _rank(sc, correct, cids)
            agg[a]["rr"].append(1.0 / r)
            agg[a]["top1"].append(1.0 if r == 1 else 0.0)
            agg[a]["pw"].append(sum(1 for n in negs if sc[correct] > sc[n]) / len(negs) if negs else 0.0)
    return {a: {"mrr": mean(v["rr"]), "top1": mean(v["top1"]), "pairwise": mean(v["pw"])}
            for a, v in agg.items()}


def deltas(metrics):
    m = {a: metrics[a]["mrr"] for a in ARMS_REQUIRED}
    return {"A_vs_X": m["A"] - m["X"], "A_vs_B": m["A"] - m["B"], "A_vs_F": m["A"] - m["F"],
            "A_vs_D": m["A"] - m["D"], "A_vs_I": m["A"] - m["I"]}


# --------------------------------------------------------------- decision ----------
def decide(metrics, eps=EPS):
    m = {a: metrics[a]["mrr"] for a in ARMS_REQUIRED}
    if max(m.values()) - min(m.values()) <= eps:
        return "INCONCLUSIVE"                 # arms not separable — setup can't discriminate
    d = deltas(metrics)
    if d["A_vs_X"] <= eps:                     # PRIMARY: no incremental gain over context
        return "CONTEXT_ONLY_EXPLAINS"
    if d["A_vs_B"] <= eps:                     # specific mapping adds nothing
        return "SCRAMBLE_EQUIVALENT"
    if d["A_vs_I"] <= eps:                     # a generic boundary reweights as well
        return "BARNUM_BOUNDARY"
    if d["A_vs_F"] <= eps:                     # etymology accounts for it
        return "ETYMOLOGY_EXPLAINS"
    if all(d[k] > eps for k in ("A_vs_X", "A_vs_B", "A_vs_F", "A_vs_D", "A_vs_I")):
        return "BOUNDARY_CONSTRAINT_SIGNAL"
    return "NO_SIGNAL"


def process_case(case, eps=EPS):
    validate_case(case)                        # raises loudly on any defect/contamination
    metrics = arm_metrics(case["items"])
    label = decide(metrics, eps)
    assert label in ALLOWED_LABELS and label not in FORBIDDEN_LABELS, label
    return {"case_id": case.get("case_id"), "label": label,
            "mrr": {a: round(metrics[a]["mrr"], 4) for a in ARMS_REQUIRED},
            "top1": {a: round(metrics[a]["top1"], 4) for a in ARMS_REQUIRED},
            "deltas": {k: round(v, 4) for k, v in deltas(metrics).items()}}


# ------------------------------------------------ blinding utility (demonstration) --
def build_packet(item, seed=0):
    """Anonymize candidates (cand_*) + hide roles/context_correct into a scorer packet + key.
    Demonstrates the blinding a real run would apply before scoring. Not used by the metric path."""
    rng = random.Random(seed)
    cands = list(item["candidates"])
    rng.shuffle(cands)
    key = {}
    packet = {"context_sentence": item.get("context_sentence", "<context>"), "candidates": []}
    for i, c in enumerate(cands, 1):
        aid = f"cand_{i}"
        key[aid] = {"orig_id": c["candidate_id"], "role": c.get("role")}
        packet["candidates"].append({"candidate_id": aid, "gloss": c.get("gloss", "")})
    key["context_correct_anon"] = next(a for a, v in key.items()
                                       if isinstance(v, dict) and v.get("orig_id") == item["context_correct"])
    return packet, key


def run_real_pilot(*a, **k):
    raise NotImplementedError("Real Track E requires explicit approval + a frozen config + a "
                              "scorer; not implemented. Synthetic mechanics only.")
