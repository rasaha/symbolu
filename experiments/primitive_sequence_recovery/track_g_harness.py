"""Track G harness — signed POLARITY-BOUNDARY mechanics (synthetic scorer output only).

Proves the Track G scoring/decision mechanics: per-arm MRR/Top-1/pairwise over candidates, the
incremental deltas (A_vs_R and A_vs_X primary, plus A_vs_B/A_vs_I/A_vs_D), the frozen-polarity /
post-hoc-invalidation gate, and the decision labels — on SYNTHETIC scorer output handed *in*. No
LLM, no network, no real data. Computes nothing about varṇa truth; it labels ranking deltas under a
frozen polarity assignment.

Guardrails: loads ONLY fixtures marked toy_not_for_scoring=true AND synthetic_only=true; rejects
real Sanskrit/varṇa/root markers, forbidden labels, malformed candidate sets/scores, and missing
polarity-assignment fields. Emits only the allowed Track G labels; never ONTOLOGICAL_SIGNAL /
SANSKRIT_PRIVILEGE / a prior-track SIGNAL label. Track B remains BLOCKED. See TRACK_G_* docs.
"""
from __future__ import annotations

import json
import pathlib
import random
from statistics import mean

ARMS_REQUIRED = ("A", "R", "B", "I", "X", "D")   # real, random-flip, scrambled, Barnum, context, dict
ALLOWED_LABELS = ("POLARITY_BOUNDARY_SIGNAL", "RANDOM_POLARITY_EXPLAINS", "CONTEXT_ONLY_EXPLAINS",
                  "SCRAMBLE_EQUIVALENT", "BARNUM_POLARITY", "NO_SIGNAL", "INCONCLUSIVE",
                  "INVALID_POSTHOC_POLARITY")
FORBIDDEN_LABELS = ("ONTOLOGICAL_SIGNAL", "EXPERIENTIAL_WEATHER_SIGNAL", "SANSKRIT_PRIVILEGE",
                    "BOUNDARY_CONSTRAINT_SIGNAL", "INFERENCE_STEERING_SIGNAL", "BOUNDARY_ONTOLOGICAL")
BANNED_REAL = ("sanskrit", "varṇa", "varna", "vṛtti", "vritti", "devanagari", "iast", "dhātu",
               "dhatu")
_PA_FIELDS = ("assigned_before_scoring", "frozen", "expected_relation", "expected_pole",
              "selected_axis_ids", "assignment_author")
_RELATIONS = ("direct", "contrast", "excluded")
EPS = 0.02


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
    pa = case.get("polarity_assignment")
    if not isinstance(pa, dict) or any(k not in pa for k in _PA_FIELDS):
        raise RejectedFixture("polarity_assignment missing/incomplete")
    if pa.get("expected_relation") not in _RELATIONS:
        raise RejectedFixture("expected_relation not in direct/contrast/excluded")
    items = case.get("items")
    if not items:
        raise RejectedFixture("no items")
    for it in items:
        cands = it.get("candidates", [])
        cids = [c.get("candidate_id") for c in cands]
        if len(cids) < 3:
            raise RejectedFixture("malformed candidate set: <3 candidates")
        if len(set(cids)) != len(cids):
            raise RejectedFixture("duplicate candidate_id")
        roles = [c.get("role") for c in cands]
        if roles.count("target") != 1:
            raise RejectedFixture("need exactly one target candidate")
        if it.get("target") not in cids:
            raise RejectedFixture("target id not among candidates")
        sc = it.get("arm_scores", {})
        for a in ARMS_REQUIRED:
            if a not in sc:
                raise RejectedFixture(f"scorer output missing arm {a}")
            for cid in cids:
                if not _num01(sc[a].get(cid)):
                    raise RejectedFixture(f"missing/invalid score {a}/{cid}")


# --------------------------------------------------------------- metrics -----------
def _rank(scores, target, cids):
    return sorted(cids, key=lambda c: (-scores[c], c)).index(target) + 1


def arm_metrics(items):
    agg = {a: {"rr": [], "top1": [], "pw": []} for a in ARMS_REQUIRED}
    for it in items:
        cids = [c["candidate_id"] for c in it["candidates"]]
        target = it["target"]
        negs = [c for c in cids if c != target]
        for a in ARMS_REQUIRED:
            sc = it["arm_scores"][a]
            r = _rank(sc, target, cids)
            agg[a]["rr"].append(1.0 / r)
            agg[a]["top1"].append(1.0 if r == 1 else 0.0)
            agg[a]["pw"].append(sum(1 for n in negs if sc[target] > sc[n]) / len(negs) if negs else 0.0)
    return {a: {"mrr": mean(v["rr"]), "top1": mean(v["top1"]), "pairwise": mean(v["pw"])}
            for a, v in agg.items()}


def deltas(metrics):
    m = {a: metrics[a]["mrr"] for a in ARMS_REQUIRED}
    return {"A_vs_R": m["A"] - m["R"], "A_vs_X": m["A"] - m["X"], "A_vs_B": m["A"] - m["B"],
            "A_vs_I": m["A"] - m["I"], "A_vs_D": m["A"] - m["D"]}


# --------------------------------------------------------------- decision ----------
def _posthoc_invalid(pa):
    return (pa.get("assigned_before_scoring") is not True or pa.get("frozen") is not True
            or pa.get("posthoc_mutated") is True)


def decide(metrics, eps=EPS):
    m = {a: metrics[a]["mrr"] for a in ARMS_REQUIRED}
    if max(m.values()) - min(m.values()) <= eps:
        return "INCONCLUSIVE"                        # arms not separable
    d = deltas(metrics)
    if d["A_vs_R"] <= eps:                            # PRIMARY: sign carries no information
        return "RANDOM_POLARITY_EXPLAINS"
    if d["A_vs_X"] <= eps:                            # PRIMARY: no incremental gain over context
        return "CONTEXT_ONLY_EXPLAINS"
    if d["A_vs_B"] <= eps:                            # specific varṇa→axis mapping adds nothing
        return "SCRAMBLE_EQUIVALENT"
    if d["A_vs_I"] <= eps:                            # a generic polarity reweights as well
        return "BARNUM_POLARITY"
    if all(d[k] > eps for k in ("A_vs_R", "A_vs_X", "A_vs_B", "A_vs_I", "A_vs_D")):
        return "POLARITY_BOUNDARY_SIGNAL"
    return "NO_SIGNAL"


def process_case(case, eps=EPS):
    validate_case(case)
    pa = case["polarity_assignment"]
    if _posthoc_invalid(pa):                          # frozen/pre-registration violated
        label, metrics = "INVALID_POSTHOC_POLARITY", None
    elif pa.get("expected_relation") == "excluded":   # pre-registered as not-scored
        label, metrics = "INCONCLUSIVE", None
    else:
        metrics = arm_metrics(case["items"])
        label = decide(metrics, eps)
    assert label in ALLOWED_LABELS and label not in FORBIDDEN_LABELS, label
    out = {"case_id": case.get("case_id"), "label": label}
    if metrics is not None:
        out["mrr"] = {a: round(metrics[a]["mrr"], 4) for a in ARMS_REQUIRED}
        out["deltas"] = {k: round(v, 4) for k, v in deltas(metrics).items()}
    return out


# ------------------------------------------------ blinding utility (demonstration) --
def build_packet(item, pa, seed=0):
    """Anonymize candidates (cand_*), hide roles, target, and the polarity direction into a scorer
    packet + key. Demonstrates the blinding a real run applies. Not used by the metric path."""
    rng = random.Random(seed)
    cands = list(item["candidates"])
    rng.shuffle(cands)
    key, packet = {"hidden_polarity_relation": pa.get("expected_relation"),
                   "hidden_expected_pole": pa.get("expected_pole")}, {"candidates": []}
    for i, c in enumerate(cands, 1):
        aid = f"cand_{i}"
        key[aid] = {"orig_id": c["candidate_id"], "role": c.get("role")}
        packet["candidates"].append({"candidate_id": aid, "gloss": c.get("gloss", "")})
    key["target_anon"] = next(a for a, v in key.items()
                              if isinstance(v, dict) and v.get("orig_id") == item["target"])
    return packet, key


def run_real_pilot(*a, **k):
    raise NotImplementedError("Real Track G requires explicit approval + a frozen config + a "
                              "scorer; not implemented. Synthetic mechanics only.")
