#!/usr/bin/env python3
"""B1.1 per-judge diagnostic — how each judge LLM independently scored A vs each control.

Reads the 3 judge output files + the packet truth_map; reports, PER JUDGE, the A-win point estimate for
each comparison (word-clustered bootstrap CI for the 3 primaries), plus each judge's parse/repair/tie
profile. NO models, NO re-scoring of the frozen verdict (that stays in run_b1_1_scorer.py). Diagnostic
only — a verdict does not unblock Track B. Structure, not validated meaning.

    python3 experiments/primitive_sequence_recovery/run_b1_1_per_judge_breakdown.py
"""
from __future__ import annotations
import collections, json, pathlib, random, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_llm_judge as J
cfg = json.loads((HERE / "b1_1_scorer_config.json").read_text(encoding="utf-8"))
PRIMARY = cfg["primary_comparisons"]
SECONDARY = cfg["secondary_comparisons"]
ALL_COMP = PRIMARY + SECONDARY
N_BOOT, BOOT_SEED = cfg["ci_policy"]["n_boot"], cfg["ci_policy"]["seed"]
OUTDIR = HERE / "b1_1_judge_outputs"
PKT_MANIFEST = HERE / "b1_1_judge_packets" / "blinded_pairwise_packet_manifest.json"
FLAGGED = ("tie_no_preference", "both_bad")


def a_win(choice, a_pos):
    if choice == "output_1_better":
        return 1.0 if a_pos == 1 else 0.0
    if choice == "output_2_better":
        return 1.0 if a_pos == 2 else 0.0
    return 0.5


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def pct(s, q):
    return s[min(len(s) - 1, max(0, int(round(q / 100 * (len(s) - 1)))))] if s else float("nan")


truth = json.loads(PKT_MANIFEST.read_text(encoding="utf-8"))["B1_1_BLINDED_PACKET_MANIFEST"]["truth_map"]
judges = []
recs_by_judge = {}
for jid in J.DECLARED_JUDGES:
    slug = J.judge_slug(jid)
    p = OUTDIR / f"b1_judge_responses_{slug}.jsonl"
    if not p.exists():
        continue
    judges.append(slug)
    recs_by_judge[slug] = {r["display_id"]: r for r in
                           (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
                           if r.get("kind") == "real"}

# per-judge A-win by comparison (+ word groups for primary CIs) and profile
per_judge = {}
for slug in judges:
    by_comp = collections.defaultdict(lambda: collections.defaultdict(list))   # comp -> word -> [awin]
    n, parse_fail, repaired, tie, awin_all = 0, 0, 0, 0, []
    for did, tm in truth.items():
        r = recs_by_judge[slug].get(did)
        if r is None:
            continue
        w = a_win(r["choice"], tm["a_output_position"])
        by_comp[tm["comparison"]][tm["target_word"]].append(w)
        awin_all.append(w)
        n += 1
        parse_fail += int(not r.get("parse_ok"))
        repaired += int(bool(r.get("parse_repair")))
        tie += int((not r.get("parse_ok")) or r.get("choice") in FLAGGED)
    comp_point = {c: mean([v for wd in by_comp[c].values() for v in wd]) for c in ALL_COMP}
    # word-clustered bootstrap CI for the 3 primaries only (cheap)
    rng = random.Random(BOOT_SEED)
    comp_ci = {}
    for c in PRIMARY:
        words = sorted(by_comp[c])
        boot = []
        for _ in range(N_BOOT):
            samp = [rng.choice(words) for _ in range(len(words))]
            boot.append(mean([v for wd in samp for v in by_comp[c][wd]]))
        boot.sort()
        comp_ci[c] = [pct(boot, 2.5), pct(boot, 97.5)]
    per_judge[slug] = {"n": n, "parse_fail": parse_fail, "repaired": repaired, "tie": tie,
                       "tie_rate": tie / n if n else 0.0, "awin_overall": mean(awin_all),
                       "comp_point": comp_point, "primary_ci": comp_ci}

# aggregate (across judges, per packet) for reference
agg_point = {}
for c in ALL_COMP:
    vals = []
    for did, tm in truth.items():
        if tm["comparison"] != c:
            continue
        ws = [a_win(recs_by_judge[s][did]["choice"], tm["a_output_position"])
              for s in judges if did in recs_by_judge[s]]
        if ws:
            vals.append(mean(ws))
    agg_point[c] = mean(vals)

report = {"artifact": "b1_1_per_judge_breakdown", "judges": judges,
          "per_judge": per_judge, "aggregate_point": agg_point,
          "note": "Diagnostic only. Frozen verdict is in run_b1_1_scorer.py; a verdict does not unblock "
                  "Track B. A-win > 0.5 = judge prefers A over the control. Structure, not validated meaning.",
          "anchors": {"b1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED"}}
(HERE / "B1_1_PER_JUDGE_BREAKDOWN.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                                    encoding="utf-8")

# ---- print ----
print("Per-judge A-win by comparison (point estimate; >0.5 = judge prefers A):")
hdr = f"{'comparison':<18}" + "".join(f"{s.split('-Instruct')[0][:14]:>15}" for s in judges) + f"{'AGG':>9}"
print(hdr)
for c in ALL_COMP:
    star = "*" if c in PRIMARY else " "
    line = f"{star}{c:<17}" + "".join(f"{per_judge[s]['comp_point'][c]:>15.3f}" for s in judges)
    print(line + f"{agg_point[c]:>9.3f}")
print("\nPrimary 95% CI per judge (word-clustered bootstrap):")
for c in PRIMARY:
    print(f"  {c:<18}" + "  ".join(f"{s.split('-Instruct')[0][:12]}=[{per_judge[s]['primary_ci'][c][0]:.3f},"
                                   f"{per_judge[s]['primary_ci'][c][1]:.3f}]" for s in judges))
print("\nPer-judge profile:")
print(f"{'judge':<26}{'n':>6}{'parse_fail':>11}{'repaired':>9}{'tie_rate':>9}{'A-win_all':>10}")
for s in judges:
    pj = per_judge[s]
    print(f"{s:<26}{pj['n']:>6}{pj['parse_fail']:>11}{pj['repaired']:>9}{pj['tie_rate']:>9.3f}{pj['awin_overall']:>10.3f}")
print("\nwrote B1_1_PER_JUDGE_BREAKDOWN.json | diagnostic only; Track B BLOCKED.")
