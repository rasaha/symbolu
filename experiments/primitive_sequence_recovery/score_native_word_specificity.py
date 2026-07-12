#!/usr/bin/env python3
"""Phase 4 — offline scoring/analysis for the native word-specificity run. NO model calls.

Order is enforced: (1) re-verify the raw-evidence freeze hashes; ONLY THEN (2) load the internal answer key and
score. Computes the frozen primary contrast (Δ = Acc(T) − max(Acc(X),Acc(R),Acc(G),Acc(F))) with a paired cluster
bootstrap over words (BCa 95% CI) and a packet↔word permutation test; per-arm Clopper–Pearson CIs; per-family
direction; the precommitted flagged-word sensitivity analysis; position/shortcut diagnostics; and the frozen
outcome taxonomy. NEVER modifies raw evidence. Refuses to run without a valid freeze declaration.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np
from scipy.stats import beta, norm

import native_ws_runlib as R

HERE = pathlib.Path(__file__).resolve().parent
KEY_PATH = R.V2 / "internal" / "answer_key.json"               # loaded ONLY after the freeze is verified
FLAGGED_WORDS = ["bhaya", "duḥkha", "sukha", "deha"]
CONTROLS = ["X", "R", "G", "F"]
CHANCE = 1.0 / 6.0
SAME_VALENCE = {"A": ["bhaya", "duḥkha"], "B": ["sukha", "yoga"]}
BOOT = 10000
PERM = 10000
BOOT_SEED = 20260908
PERM_SEED = 20260909


def _canonical(records):
    return json.dumps(sorted(records, key=lambda r: r["trial_id"]), ensure_ascii=False, sort_keys=True).encode("utf-8")


def verify_freeze(evidence_root):
    root = pathlib.Path(evidence_root)
    decl_path = root / "raw_evidence_freeze.json"
    if not decl_path.exists():
        raise SystemExit("REFUSING to score: no raw_evidence_freeze.json — run the freeze phase first")
    decl = json.loads(decl_path.read_text(encoding="utf-8"))
    if not decl.get("frozen"):
        raise SystemExit("REFUSING to score: freeze declaration is not marked frozen")
    for eid, meta in decl["per_evaluator"].items():
        if not meta.get("present"):
            continue
        recs = {}
        with open(root / eid / "responses.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line); recs[r["trial_id"]] = r
        got = hashlib.sha256(_canonical(list(recs.values()))).hexdigest()
        if got != meta["canonical_sha256"]:
            raise SystemExit(f"REFUSING to score: evidence hash mismatch for {eid} (raw evidence changed)")
    return decl


def load_presentations(evidence_root, decl):
    key = {k["opaque_trial_id"]: k for k in json.loads(KEY_PATH.read_text(encoding="utf-8"))["key"]}
    trials = {t["trial_id"]: t for t in R.load_trials()}
    gloss_at = {tid: {c["label"]: c["gloss"] for c in t["candidates"]} for tid, t in trials.items()}
    word_gloss = {}                                           # word -> its correct gloss (from any trial it targets)
    for tid, k in key.items():
        word_gloss[k["target_word"]] = gloss_at[tid][k["correct_label"]]
    root = pathlib.Path(evidence_root)
    P = []
    for eid, meta in decl["per_evaluator"].items():
        if not meta.get("present"):
            continue
        fam = meta.get("family") or eid
        with open(root / eid / "responses.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line); tid = r["trial_id"]; k = key[tid]
                chosen = r.get("parsed_choice")
                chosen_gloss = gloss_at[tid].get(chosen) if chosen else None
                P.append({"evaluator": eid, "family": fam, "set": k["set"], "arm": k["arm"],
                          "word": k["target_word"], "correct_gloss": word_gloss[k["target_word"]],
                          "chosen_gloss": chosen_gloss,
                          "correct": int(chosen_gloss is not None and chosen_gloss == word_gloss[k["target_word"]])})
    return P, word_gloss


# ---------- statistics ----------
def acc(rows):
    return float(np.mean([r["correct"] for r in rows])) if rows else 0.0


def clopper_pearson(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return round(float(lo), 4), round(float(hi), 4)


def delta_from(rows):
    by = {a: [r for r in rows if r["arm"] == a] for a in ["T"] + CONTROLS}
    if not by["T"] or any(not by[a] for a in CONTROLS):
        return None
    return acc(by["T"]) - max(acc(by[a]) for a in CONTROLS)


def bca_ci(rows, words, rng, B=None):
    B = B or BOOT
    """Paired cluster bootstrap over WORDS with BCa 95% CI on Δ."""
    by_word = {w: [r for r in rows if r["word"] == w] for w in words}
    theta = delta_from(rows)
    if theta is None:
        return None
    boots = []
    for _ in range(B):
        pick = rng.choice(words, size=len(words), replace=True)
        rr = [r for w in pick for r in by_word[w]]
        d = delta_from(rr)
        if d is not None:
            boots.append(d)
    boots = np.array(boots)
    z0 = norm.ppf(np.mean(boots < theta)) if 0 < np.mean(boots < theta) < 1 else 0.0
    jack = []
    for i in range(len(words)):
        rr = [r for j, w in enumerate(words) if j != i for r in by_word[w]]
        d = delta_from(rr)
        if d is not None:
            jack.append(d)
    jack = np.array(jack); jbar = jack.mean()
    num = np.sum((jbar - jack) ** 3); den = 6.0 * (np.sum((jbar - jack) ** 2) ** 1.5)
    a = num / den if den != 0 else 0.0
    def adj(alpha):
        z = norm.ppf(alpha)
        p = norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z)))
        return float(np.quantile(boots, p))
    return {"delta": round(theta, 4), "ci_lower": round(adj(0.025), 4), "ci_upper": round(adj(0.975), 4),
            "z0": round(float(z0), 4), "accel": round(float(a), 5), "n_boot": int(len(boots))}


def permutation_p(rows, words, rng, n=None):
    n = n or PERM
    """Packet↔word permutation: reassign word identities within the set (random bijection), recompute Δ."""
    theta = delta_from(rows)
    if theta is None:
        return None
    ge = 0; done = 0
    words = list(words)
    for _ in range(n):
        perm = words[:]; rng.shuffle(perm)
        sigma = dict(zip(words, perm))
        gmap = {w: rows_word_gloss[w] for w in words}          # correct gloss of the permuted word
        rr = [{"arm": r["arm"], "correct": int(r["chosen_gloss"] is not None
                                               and r["chosen_gloss"] == gmap[sigma[r["word"]]])} for r in rows]
        d = delta_from(rr)
        if d is not None:
            done += 1; ge += int(d >= theta)
    return {"p_value": round((ge + 1) / (done + 1), 5), "n_perm": done}


rows_word_gloss = {}   # filled in score()


def score(evidence_root, out_path):
    decl = verify_freeze(evidence_root)                        # (1) verify BEFORE any key access
    P, word_gloss = load_presentations(evidence_root, decl)    # (2) key loaded here, post-verification
    global rows_word_gloss
    rows_word_gloss = word_gloss
    rng = np.random.default_rng(BOOT_SEED)
    prng = np.random.default_rng(PERM_SEED)

    def block(rows, words):
        arms = {}
        for a in ["T", "S"] + CONTROLS:
            ra = [r for r in rows if r["arm"] == a]
            k = sum(r["correct"] for r in ra); n = len(ra)
            arms[a] = {"accuracy": round(k / n, 4) if n else None, "n": n,
                       "cp95": clopper_pearson(k, n) if n else None}
        return {"per_arm": arms,
                "bca": bca_ci(rows, words, np.random.default_rng(rng.integers(1 << 31))),
                "permutation": permutation_p(rows, words, np.random.default_rng(prng.integers(1 << 31)))}

    setA_words = ["aśva", "bala", "bhaya", "duḥkha", "gaja", "megha"]
    setB_words = ["bīja", "sukha", "deha", "lavaṇa", "yoga", "vṛkṣa"]
    A = [r for r in P if r["set"] == "A"]; B = [r for r in P if r["set"] == "B"]

    result = {"analysis": "native_word_specificity", "packet_commit": "42f38d57", "audit_commit": "fc15a0d8",
              "freeze_verified": True, "chance": round(CHANCE, 4), "n_presentations": len(P),
              "families": sorted({r["family"] for r in P}),
              "primary": {"set_A": block(A, setA_words), "set_B": block(B, setB_words),
                          "overall": block(P, setA_words + setB_words)},
              "per_family_delta": {fam: delta_from([r for r in P if r["family"] == fam])
                                   for fam in sorted({r["family"] for r in P})},
              "flagged_word_sensitivity": {
                  "flagged_words": FLAGGED_WORDS,
                  "set_A_excluding_flagged": block([r for r in A if r["word"] not in FLAGGED_WORDS],
                                                   [w for w in setA_words if w not in FLAGGED_WORDS]),
                  "set_B_excluding_flagged": block([r for r in B if r["word"] not in FLAGGED_WORDS],
                                                   [w for w in setB_words if w not in FLAGGED_WORDS]),
                  "caveat": "Source-intrinsic semantic proximity is part of the mapping under test, but because the "
                            "upstream lexicon may have been authored with semantic awareness, concentration of the "
                            "effect in these words limits causal interpretation."},
              "diagnostics": {
                  "same_valence_accuracy": {s: round(acc([r for r in P if r["set"] == s
                                                          and r["word"] in SAME_VALENCE[s] and r["arm"] == "T"]), 4)
                                            for s in ("A", "B")},
                  "F_accuracy": round(acc([r for r in P if r["arm"] == "F"]), 4),
                  "R_accuracy": round(acc([r for r in P if r["arm"] == "R"]), 4),
                  "T_accuracy": round(acc([r for r in P if r["arm"] == "T"]), 4),
                  "per_word_confusion": {w: {} for w in setA_words + setB_words}},
              "missing_invalid": {eid: decl["per_evaluator"][eid].get("missing_invalid_rate")
                                  for eid in decl["per_evaluator"]}}

    # per-word confusion (chosen gloss distribution on the true arm)
    for r in P:
        if r["arm"] == "T":
            c = result["diagnostics"]["per_word_confusion"][r["word"]]
            g = r["chosen_gloss"] or "MISSING"
            c[g] = c.get(g, 0) + 1

    # frozen outcome taxonomy
    dA = result["primary"]["set_A"]["bca"]; dB = result["primary"]["set_B"]["bca"]
    fam_dirs = [d for d in result["per_family_delta"].values() if d is not None]
    tax = "NO_WORD_SPECIFIC_SIGNAL"
    if dA and dA["ci_lower"] > 0:
        if dA["delta"] >= 0.15 and dB and dB["ci_lower"] > 0 and len(fam_dirs) >= 3 and all(d > 0 for d in fam_dirs):
            tax = "WORD_SPECIFIC_SIGNAL_REPLICATES"
        elif dB and dB["ci_lower"] <= 0:
            tax = "IDEAL_SET_ONLY_NOT_REPLICATED"
    Tacc = result["diagnostics"]["T_accuracy"]
    if result["diagnostics"]["F_accuracy"] >= Tacc - 0.02 and Tacc > CHANCE:
        tax = "STRUCTURAL_SHORTCUT_EXPLAINS"
    elif result["diagnostics"]["R_accuracy"] >= Tacc - 0.02 and Tacc > CHANCE and tax == "NO_WORD_SPECIFIC_SIGNAL":
        tax = "RANDOM_ASSIGNMENT_EXPLAINS"
    result["outcome_taxonomy"] = tax
    result["success_criteria_note"] = ("primary requires Set A Δ≥0.15 & CI-lower>0, Set B CI-lower>0, direction "
                                        "consistent across ≥3 families, same-valence>chance, F & length ~ chance")

    R.write_json_atomic(pathlib.Path(out_path), result)
    print(json.dumps({"outcome_taxonomy": tax,
                      "set_A_delta": dA, "set_B_delta": dB,
                      "T_acc": Tacc, "F_acc": result["diagnostics"]["F_accuracy"],
                      "R_acc": result["diagnostics"]["R_accuracy"],
                      "per_family_delta": result["per_family_delta"], "out": str(out_path)}, indent=2,
                     ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", required=True)
    ap.add_argument("--out", default=str(HERE / "native_ws_analysis" / "native_word_specificity_analysis.json"))
    a = ap.parse_args()
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sys.exit(score(a.evidence_root, a.out))


if __name__ == "__main__":
    main()
