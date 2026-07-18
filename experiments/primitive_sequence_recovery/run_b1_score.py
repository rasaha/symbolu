#!/usr/bin/env python3
"""B1 SCORER — maps blinded judge choices to A-win via the truth map and emits the single verdict.

This is the ONLY step that sees the truth map (which neutral output was A). It:
  1. re-verifies the 11 frozen B0 hashes (mismatch -> INVALID_POSTHOC);
  2. applies the frozen attention-check exclusion per judge (fail >1 OR >25%);
  3. per packet: each surviving judge's choice -> A-win in {0,0.5,1} via truth (tie/both_bad -> 0.5,
     both_bad flagged); majority across judges = MEDIAN of their A-win scores (stays in {0,0.5,1});
  4. aggregates per co-primary (A vs D/R/S/C/X), item-clustered by (key_word, task), PRIMARY stratum;
  5. frozen stats: paired bootstrap (n_boot=2000, seed=60617) -> Holm-Bonferroni across the 5
     co-primaries -> CI lower bound > 0.5 each -> apply_verdict (A must beat ALL five);
  6. reports privative stratum SEPARATELY, inter-judge agreement, per-arm win rates, flagged/repair
     rates, and a T4 correctness diagnostic;
  7. writes b1_score_result.json and prints the verdict block.

Reuses the FROZEN stats verbatim (clustered_bootstrap_ci / holm_bonferroni / apply_verdict from
b1_dry_run_harness). CPU-only, no model. Emitting the verdict does NOT unblock Track B.

    python3 experiments/primitive_sequence_recovery/run_b1_score.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B            # noqa: E402  frozen stats + constants

FREEZE_RECORD = HERE / "B0_FREEZE_RECORD.json"
TRUTH_FILE = HERE / "b1_judge_packets_full.jsonl"     # scorer-only (has the truth map)
JUDGE_TAG = "v2"
JUDGE_SLUGS = ("Llama-3-1-8B-Instruct", "Meta-Llama-3-8B-Instruct", "gemma-2-9b-it")

FLAGGED = ("tie_no_preference", "both_bad")


def _fail(msg):
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def verify_frozen():
    rec = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))["B0_FREEZE_RECORD"]
    bad = [a["path"] for a in rec["bound_artifacts"]
           if hashlib.sha256((REPO / a["path"]).read_bytes()).hexdigest() != a["sha256"]]
    return (not bad), bad


def a_win(choice, truth):
    """Judge choice -> A-win in {0,0.5,1} using the packet truth map {'Output 1':arm,'Output 2':arm}."""
    if choice == "output_1_better":
        return 1.0 if truth.get("Output 1") == "A" else 0.0
    if choice == "output_2_better":
        return 1.0 if truth.get("Output 2") == "A" else 0.0
    return 0.5                                          # tie_no_preference / both_bad


def load_truth():
    if not TRUTH_FILE.exists():
        _fail(f"{TRUTH_FILE} not found (run the packet builder on this pod first).")
    truth = {}
    for ln in TRUTH_FILE.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        p = json.loads(ln)
        parts = p["packet_id"].split("|")              # kw | task | model | seed | A_vs_ctrl
        kw = p["key_word"]
        truth[p["display_id"]] = {
            "control": p["control_arm"], "key_word": kw,
            "task": parts[1] if len(parts) >= 2 else "?",
            "model": parts[2] if len(parts) >= 3 else "?",
            "seed": parts[3] if len(parts) >= 4 else "?",
            "stratum": "primary" if kw in B.PRIMARY_WORDS else "privative",
            "truth": p["truth"],
        }
    return truth


def load_judges():
    """Return ({judge: {display_id: choice}}, kept_judges, per_judge_attn) applying the frozen
    attention-exclusion rule per judge."""
    import run_b1_llm_judge as J
    attn_correct = {a["display_id"]: a["_attn_correct"] for a in J.build_attention_checks()}
    choices, kept, attn_info = {}, [], {}
    for slug in JUDGE_SLUGS:
        path = HERE / f"b1_judge_responses_{slug}_{JUDGE_TAG}.jsonl"
        if not path.exists():
            _fail(f"missing judge file {path.name}")
        real, af, n_attn, repaired = {}, 0, 0, 0
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get("parse_repair"):
                repaired += 1
            if r["kind"] == "attn":
                n_attn += 1
                if r["choice"] != attn_correct.get(r["display_id"]):
                    af += 1
            else:
                real[r["display_id"]] = r["choice"]
        excluded = J.attention_excluded(af, n_attn)
        attn_info[slug] = {"attn_fail": af, "n_attn": n_attn, "excluded": excluded, "repaired": repaired}
        if not excluded:
            kept.append(slug)
            choices[slug] = real
    return choices, kept, attn_info


def aggregate(choices, kept, truth, stratum):
    """Per co-primary: item-clustered (key_word,task) A-win. Returns {control: {item_scores, win_rate,
    n_items, n_packets}} plus a flagged (tie/both_bad) count."""
    # control -> item(key_word,task) -> list of per-packet majority A-win scores
    buckets = {c: {} for c in B.CO_PRIMARIES}
    flagged = 0
    n_packets = 0
    for did, meta in truth.items():
        if meta["stratum"] != stratum:
            continue
        c = meta["control"]
        if c not in buckets:
            continue
        votes = []
        for j in kept:
            ch = choices[j].get(did)
            if ch is None:
                continue
            if ch in FLAGGED:
                flagged += 1
            votes.append(a_win(ch, meta["truth"]))
        if not votes:
            continue
        pkt = statistics.median(votes)                 # majority across judges, stays in {0,0.5,1}
        buckets[c].setdefault((meta["key_word"], meta["task"]), []).append(pkt)
        n_packets += 1
    out = {}
    for c, items in buckets.items():
        item_scores = [statistics.mean(v) for _k, v in sorted(items.items())]
        out[c] = {"item_scores": item_scores,
                  "win_rate": statistics.mean(item_scores) if item_scores else float("nan"),
                  "n_items": len(item_scores),
                  "n_packets": sum(len(v) for v in items.values())}
    return out, flagged, n_packets


def score_stratum(agg):
    per, pvals = {}, {}
    for c in B.CO_PRIMARIES:
        scores = agg[c]["item_scores"]
        if not scores:
            per[c] = {"win_rate": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"),
                      "p": 1.0, "n_items": 0}
            pvals[c] = 1.0
            continue
        mean, lo, hi, p = B.clustered_bootstrap_ci(scores, n_boot=B.BOOTSTRAP["n_boot"],
                                                   seed=B.BOOTSTRAP["seed"])
        per[c] = {"win_rate": round(mean, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                  "p": p, "n_items": agg[c]["n_items"]}
        pvals[c] = p
    holm = B.holm_bonferroni(pvals)
    for c in B.CO_PRIMARIES:
        per[c]["holm_p"], per[c]["holm_reject"] = round(holm[c][0], 4), holm[c][1]
    return per


def inter_judge_agreement(choices, kept, truth):
    if len(kept) < 2:
        return None
    dids = [d for d in truth if all(d in choices[j] for j in kept)]
    unanimous = 0
    for d in dids:
        aw = {a_win(choices[j][d], truth[d]["truth"]) for j in kept}
        if len(aw) == 1:
            unanimous += 1
    return {"n_common_packets": len(dids),
            "unanimous_a_win_rate": round(unanimous / len(dids), 4) if dids else None,
            "n_judges_kept": len(kept)}


def t4_correctness(choices, kept, truth):
    """Diagnostic (not an auto-kill): on T4 explanation packets, how often is A's output flagged with a
    correctness problem vs the control's, per the judges' correctness_flag. Reported for human review."""
    # correctness_flag lives in the judge files; reload lightly for T4 only
    a_prob = ctrl_prob = n = 0
    flags = {}
    for slug in kept:
        path = HERE / f"b1_judge_responses_{slug}_{JUDGE_TAG}.jsonl"
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get("kind") != "real":
                continue
            flags.setdefault(r["display_id"], []).append(r.get("correctness_flag", "none"))
    for did, meta in truth.items():
        if meta["task"] != "T4":
            continue
        a_side = "Output 1" if meta["truth"].get("Output 1") == "A" else "Output 2"
        c_side = "Output 2" if a_side == "Output 1" else "Output 1"
        a_key = "output_1_problem" if a_side == "Output 1" else "output_2_problem"
        c_key = "output_1_problem" if c_side == "Output 1" else "output_2_problem"
        for f in flags.get(did, []):
            n += 1
            if f in (a_key, "both_problem"):
                a_prob += 1
            if f in (c_key, "both_problem"):
                ctrl_prob += 1
    return {"t4_judgements": n, "A_correctness_problem": a_prob, "control_correctness_problem": ctrl_prob,
            "note": "diagnostic only; A worse than control on T4 would qualify the interpretation of any A win"}


def main():
    ok, bad = verify_frozen()
    print(f"[{'ok' if ok else 'FAIL'}] frozen integrity" + (f" — CHANGED: {bad}" if bad else ""))
    choices, kept, attn = load_judges()
    print(f"[ok] judges kept: {kept} (of {list(JUDGE_SLUGS)})")
    for s, a in attn.items():
        print(f"     {s}: attn_fail {a['attn_fail']}/{a['n_attn']} "
              f"-> {'EXCLUDED' if a['excluded'] else 'kept'} | repaired {a['repaired']}")
    truth = load_truth()

    agg_p, flagged_p, npkt_p = aggregate(choices, kept, truth, "primary")
    per_primary = score_stratum(agg_p)
    agg_v, flagged_v, npkt_v = aggregate(choices, kept, truth, "privative")
    per_priv = score_stratum(agg_v)

    flags = {"invalid_posthoc": not ok}                # leakage clean (pre-verified); correctness = diagnostic
    verdict = B.apply_verdict({c: per_primary[c] for c in B.CO_PRIMARIES}, flags=flags)
    agree = inter_judge_agreement(choices, kept, truth)
    t4 = t4_correctness(choices, kept, truth)

    result = {"B1_SCORE_RESULT": {
        "verdict": verdict,
        "primary_co_primaries": per_primary,
        "privative_stratum_separate": per_priv,
        "kept_judges": kept, "attention": attn,
        "flagged_primary": flagged_p, "flagged_privative": flagged_v,
        "inter_judge_agreement": agree, "t4_correctness_diagnostic": t4,
        "threshold": "corrected CI lower bound > 0.5 for EACH of D/R/S/C/X (A must beat all five)",
        "bootstrap": B.BOOTSTRAP, "n_packets_primary": npkt_p, "n_packets_privative": npkt_v,
        "evidence_scope": "internal LLM-judge (Llama-3.1-8B + Meta-Llama-3-8B + gemma-2-9b-it); "
                          "human replication required if positive; does NOT unblock Track B",
        "caveat_meta_llama3_repair": "Meta-Llama-3-8B relied on missing-final-brace repair for ~55% of "
                                     "verdicts (safe, flagged, choice unchanged) — see V2 provenance",
        "track_b": "BLOCKED",
        "note": "Structure, not validated meaning. Verdict does not unblock Track B."}}
    (HERE / "b1_score_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("\n================ B1 SCORE ================")
    print(f"VERDICT: {verdict}")
    print(f"{'ctrl':>4} {'win_rate':>9} {'ci_lo':>7} {'ci_hi':>7} {'holm_p':>7} {'reject':>7} {'beats?':>7}")
    for c in B.CO_PRIMARIES:
        r = per_primary[c]
        beats = r["ci_lo"] > 0.5 and r["holm_reject"]
        print(f"{c:>4} {r['win_rate']:>9} {r['ci_lo']:>7} {r['ci_hi']:>7} "
              f"{r['holm_p']:>7} {str(r['holm_reject']):>7} {str(beats):>7}")
    print(f"\nprimary flagged(tie/both_bad): {flagged_p} | privative flagged: {flagged_v}")
    print(f"inter-judge unanimous A-win rate: {agree}")
    print(f"T4 correctness diagnostic: A_problem={t4['A_correctness_problem']} "
          f"control_problem={t4['control_correctness_problem']} (of {t4['t4_judgements']})")
    print(f"privative (separate): " + ", ".join(
        f"{c}:{per_priv[c]['win_rate']}[{per_priv[c]['ci_lo']},{per_priv[c]['ci_hi']}]" for c in B.CO_PRIMARIES))
    print("\nwrote b1_score_result.json | Track B BLOCKED | internal LLM-judge evidence")
    print("========================================")


if __name__ == "__main__":
    main()
