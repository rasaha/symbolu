#!/usr/bin/env python3
"""B1.1 SCORER — maps blinded judge choices -> A-win and computes the verdict per the FROZEN
b1_1_scorer_config.json. NO models. Item(word)-clustered paired bootstrap (n_boot 2000, seed 60617),
Holm-Bonferroni across the 7 co-primary comparisons, T4 correctness gate, and robustness sensitivities.

Emitting a verdict does NOT unblock Track B and does NOT reinterpret a failure as ontology signal
(no_rescue). A null (`RANDOM_OR_SCRAMBLED_MATCHES` / `*_RESONANCE_MATCHES`) is a real, reportable outcome.
Structure, not validated meaning.

    python3 experiments/primitive_sequence_recovery/run_b1_1_scorer.py
"""
from __future__ import annotations
import collections, hashlib, json, pathlib, random, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_llm_judge as J        # DECLARED_JUDGES, judge_slug, build_attention_checks, attention_excluded
cfg = json.loads((HERE / "b1_1_scorer_config.json").read_text(encoding="utf-8"))
N_BOOT = cfg["ci_policy"]["n_boot"]                      # 2000
BOOT_SEED = cfg["ci_policy"]["seed"]                    # 60617
PRIMARY = cfg["primary_comparisons"]                    # A_vs_R_deranged/domain/same
SECONDARY = cfg["secondary_comparisons"]               # A_vs_D/S/C/X
ALL_COMP = PRIMARY + SECONDARY                          # co-primary Holm set (7)
OUTDIR = HERE / "b1_1_judge_outputs"
PKT_MANIFEST = HERE / "b1_1_judge_packets" / "blinded_pairwise_packet_manifest.json"

blockers = []


def a_win(choice, a_pos):
    """A-win in {1.0, 0.0, 0.5}. tie/both_bad/parse-fallback -> 0.5 (no A-win, no A-loss)."""
    if choice == "output_1_better":
        return 1.0 if a_pos == 1 else 0.0
    if choice == "output_2_better":
        return 1.0 if a_pos == 2 else 0.0
    return 0.5


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def pctile(sorted_xs, q):
    if not sorted_xs:
        return float("nan")
    i = min(len(sorted_xs) - 1, max(0, int(round(q / 100.0 * (len(sorted_xs) - 1)))))
    return sorted_xs[i]


# ---- load truth + judge outputs ----
truth = json.loads(PKT_MANIFEST.read_text(encoding="utf-8"))["B1_1_BLINDED_PACKET_MANIFEST"]["truth_map"]
attn_correct = {a["display_id"]: a["_attn_correct"] for a in J.build_attention_checks()}
n_attn = len(attn_correct)

judges, excluded_judges = [], []
per_judge_recs = {}
for jid in J.DECLARED_JUDGES:
    slug = J.judge_slug(jid)
    p = OUTDIR / f"b1_judge_responses_{slug}.jsonl"
    if not p.exists():
        blockers.append(f"missing judge output {p.name}")
        continue
    recs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    attn_recs = [r for r in recs if r.get("kind") == "attn"]
    af = sum(1 for r in attn_recs if r.get("choice") != attn_correct.get(r["display_id"]))
    if J.attention_excluded(af, n_attn):                # frozen exclusion (no post-hoc selection)
        excluded_judges.append(slug)
        continue
    judges.append(slug)
    per_judge_recs[slug] = {r["display_id"]: r for r in recs if r.get("kind") == "real"}
if len(judges) < 3:
    blockers.append(f"only {len(judges)} judges kept (<3 min); adjudication required before scoring")


# ---- per-packet A-win aggregated across kept judges (+ parse-fail bookkeeping) ----
def packet_awins(judge_subset, drop_parse_fail=False):
    """display_id -> mean A-win across judge_subset. drop_parse_fail: skip parse-failed judge records."""
    out = {}
    for did, tm in truth.items():
        a_pos = tm["a_output_position"]
        vals = []
        for slug in judge_subset:
            r = per_judge_recs[slug].get(did)
            if r is None:
                continue
            if drop_parse_fail and not r.get("parse_ok"):
                continue
            vals.append(a_win(r["choice"], a_pos))
        if vals:
            out[did] = mean(vals)
    return out


def score_comparisons(awins):
    """Per comparison: point estimate + item(word)-clustered paired bootstrap CI + one-sided p (H0: <=0.5).
    Returns {comp: {...}} and applies Holm across the 7. Deterministic (single RNG seeded BOOT_SEED)."""
    by_comp = collections.defaultdict(lambda: collections.defaultdict(list))   # comp -> word -> [awin]
    for did, tm in truth.items():
        if did in awins:
            by_comp[tm["comparison"]][tm["target_word"]].append(awins[did])
    rng = random.Random(BOOT_SEED)
    res = {}
    for comp in ALL_COMP:                                # fixed order -> deterministic
        words = sorted(by_comp[comp])
        allv = [v for w in words for v in by_comp[comp][w]]
        point = mean(allv)
        boot = []
        for _ in range(N_BOOT):
            samp = [rng.choice(words) for _ in range(len(words))]      # resample word-clusters
            vals = [v for w in samp for v in by_comp[comp][w]]
            boot.append(mean(vals))
        boot.sort()
        ci_lo, ci_hi = pctile(boot, 2.5), pctile(boot, 97.5)
        p = (1 + sum(1 for m in boot if m <= 0.5)) / (N_BOOT + 1)       # one-sided H0: mean<=0.5
        res[comp] = {"n_packets": len(allv), "n_words": len(words), "point": point,
                     "ci95": [ci_lo, ci_hi], "raw_p_one_sided": p}
    # Holm-Bonferroni across the 7
    order = sorted(ALL_COMP, key=lambda c: res[c]["raw_p_one_sided"])
    m = len(order)
    prev = 0.0
    for i, comp in enumerate(order):
        adj = min(1.0, (m - i) * res[comp]["raw_p_one_sided"])
        adj = max(adj, prev)                            # enforce monotonicity
        prev = adj
        res[comp]["holm_p"] = adj
        res[comp]["beats"] = (adj < 0.05 and res[comp]["point"] > 0.5 and res[comp]["ci95"][0] > 0.5)
    return res


# ---- T4 correctness gate ----
def t4_correctness(judge_subset):
    a_prob, c_prob, n = 0, 0, 0
    for did, tm in truth.items():
        if tm["task_id"] != "T4":
            continue
        a_pos = tm["a_output_position"]
        for slug in judge_subset:
            r = per_judge_recs[slug].get(did)
            if r is None:
                continue
            f = r.get("correctness_flag", "none")
            a_bad = (f == "both_problem") or (a_pos == 1 and f == "output_1_problem") or (a_pos == 2 and f == "output_2_problem")
            c_bad = (f == "both_problem") or (a_pos == 1 and f == "output_2_problem") or (a_pos == 2 and f == "output_1_problem")
            a_prob += int(a_bad); c_prob += int(c_bad); n += 1
    return {"n_judgements": n, "A_problem_rate": (a_prob / n if n else 0.0),
            "control_problem_rate": (c_prob / n if n else 0.0),
            "A_minus_control": ((a_prob - c_prob) / n if n else 0.0),
            "degraded": (n > 0 and (a_prob - c_prob) / n > 0.05)}   # A meaningfully worse on T4


def verdict_of(res, t4):
    def beats(c):
        return res[c]["beats"]
    if t4["degraded"]:
        return "CORRECTNESS_DEGRADED"
    if all(beats(c) for c in ALL_COMP):
        return "LIMITED_GENERATION_UTILITY"
    if not beats("A_vs_R_deranged") and not beats("A_vs_R_domain") and not beats("A_vs_R_same"):
        return "RANDOM_OR_SCRAMBLED_MATCHES"
    if not beats("A_vs_R_deranged"):
        return "DERANGED_RESONANCE_MATCHES"
    if not beats("A_vs_R_domain"):
        return "DOMAIN_RESONANCE_MATCHES"
    if not beats("A_vs_D"):
        return "DICTIONARY_DOMINATES"
    if not beats("A_vs_C"):
        return "SURFACE_STRUCTURE_EXPLAINS"
    if beats("A_vs_X") and not any(beats(c) for c in PRIMARY + ["A_vs_D", "A_vs_S", "A_vs_C"]):
        return "NO_SIGNAL"
    return "NOT_ROBUST"


# ---- primary (all kept judges) + sensitivities ----
primary_awins = packet_awins(judges)
primary_res = score_comparisons(primary_awins) if not blockers else {}
primary_t4 = t4_correctness(judges)
primary_verdict = verdict_of(primary_res, primary_t4) if primary_res else "BLOCKED"

sens = {}
if primary_res:
    subset_no_meta = [j for j in judges if "Meta-Llama-3" not in j]
    if subset_no_meta:
        r = score_comparisons(packet_awins(subset_no_meta))
        sens["drop_Meta-Llama-3"] = {"verdict": verdict_of(r, t4_correctness(subset_no_meta)),
                                     "R_beats": {c: r[c]["beats"] for c in PRIMARY}}
    r2 = score_comparisons(packet_awins(judges, drop_parse_fail=True))
    sens["drop_parse_fail_items"] = {"verdict": verdict_of(r2, t4_correctness(judges)),
                                     "R_beats": {c: r2[c]["beats"] for c in PRIMARY}}
robust = all(s["verdict"] == primary_verdict for s in sens.values()) if sens else None

status = "BLOCKED" if blockers else "SCORED"
report = {
    "artifact": "b1_1_scorer_report", "status": status,
    "scope": "map judge choices -> A-win; verdict per FROZEN b1_1_scorer_config. NO models. no_rescue.",
    "judges_kept": judges, "judges_excluded": excluded_judges,
    "ci_policy": {"method": "item(word)-clustered paired bootstrap", "n_boot": N_BOOT, "seed": BOOT_SEED,
                  "beat": "Holm-adjusted p<0.05 AND point>0.5 AND CI-lower>0.5"},
    "per_comparison": {c: {**primary_res[c], "is_primary": c in PRIMARY} for c in ALL_COMP} if primary_res else {},
    "primary_success": (all(primary_res[c]["beats"] for c in PRIMARY) if primary_res else None),
    "t4_correctness": primary_t4,
    "verdict": primary_verdict,
    "sensitivities": sens, "verdict_robust_under_sensitivity": robust,
    "anchors": {"b1_verdict_prior": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED",
                "positive_cap": "LIMITED_GENERATION_UTILITY", "crux": "R_deranged",
                "track_g": "RANDOM_POLARITY_EXPLAINS (1fe5562)"},
    "no_rescue": cfg["no_rescue"],
    "non_claims": ["verdict does NOT unblock Track B", "no ontology validation", "no Sanskrit privilege",
                   "no semantic truth", "positive capped at LIMITED_GENERATION_UTILITY (in-architecture)"],
    "blockers": blockers,
}
(HERE / "B1_1_SCORING_REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                               encoding="utf-8")


def row(c):
    r = primary_res[c]
    star = " (PRIMARY)" if c in PRIMARY else ""
    return (f"| {c}{star} | {r['point']:.4f} | [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}] | "
            f"{r['holm_p']:.4f} | {'YES' if r['beats'] else 'no'} |")

md = [f"# B1.1 Scoring Report\n\n## Verdict: `{primary_verdict}`\n",
      "Maps blinded judge choices → A-win and applies the FROZEN scorer (item-clustered paired bootstrap, "
      "Holm-corrected). **Emitting a verdict does NOT unblock Track B and cannot rescue a failure into an "
      "ontology claim (`no_rescue`).** A positive is capped at `LIMITED_GENERATION_UTILITY` (in-architecture). "
      "Structure, not validated meaning.\n",
      f"- judges kept: {judges} · excluded: {excluded_judges or 'none'}",
      f"- bootstrap: item(word)-clustered paired, n_boot {N_BOOT}, seed {BOOT_SEED}; "
      "beat = Holm p<0.05 AND point>0.5 AND CI-lower>0.5\n",
      "| comparison | A-win | 95% CI | Holm p | beats? |", "|---|---|---|---|---|"]
md += [row(c) for c in PRIMARY + SECONDARY]
md += ["",
       f"- **primary success (A beats R_deranged AND R_domain AND R_same):** "
       f"**{all(primary_res[c]['beats'] for c in PRIMARY)}**",
       f"- **T4 correctness:** A_problem_rate {primary_t4['A_problem_rate']:.3f} vs control "
       f"{primary_t4['control_problem_rate']:.3f} (Δ {primary_t4['A_minus_control']:+.3f}) — "
       f"degraded: **{primary_t4['degraded']}**",
       "",
       "## Robustness sensitivities (non-frozen diagnostics)"]
for k, s in sens.items():
    md.append(f"- **{k}**: verdict `{s['verdict']}` · R-beats {s['R_beats']}")
md += [f"- **verdict robust under sensitivities:** {robust}", "",
       f"## Verdict: `{primary_verdict}`", "",
       "```",
       f"verdict:              {primary_verdict}",
       f"primary_success:      {all(primary_res[c]['beats'] for c in PRIMARY)}",
       f"robust:               {robust}",
       f"prior B1 verdict:     RANDOM_OR_SCRAMBLED_MATCHES",
       f"Track B:              BLOCKED (a verdict does not unblock it)",
       f"positive cap:         LIMITED_GENERATION_UTILITY",
       "```",
       "Preserved: Track G `RANDOM_POLARITY_EXPLAINS` (1fe5562). `R_deranged` was the crux. "
       "**Structure, not validated meaning.**"]
(HERE / "B1_1_SCORING_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"STATUS: {status}")
if primary_res:
    print(f"VERDICT: {primary_verdict} | primary_success {all(primary_res[c]['beats'] for c in PRIMARY)} "
          f"| robust {robust}")
    print(f"{'comparison':<20} {'A-win':>7} {'CI-lo':>7} {'CI-hi':>7} {'holm_p':>7} beats")
    for c in PRIMARY + SECONDARY:
        r = primary_res[c]
        print(f"{c:<20} {r['point']:>7.4f} {r['ci95'][0]:>7.4f} {r['ci95'][1]:>7.4f} "
              f"{r['holm_p']:>7.4f} {'YES' if r['beats'] else 'no'}{'  *primary' if c in PRIMARY else ''}")
    print(f"T4 correctness: A {primary_t4['A_problem_rate']:.3f} vs ctrl {primary_t4['control_problem_rate']:.3f} "
          f"-> degraded {primary_t4['degraded']}")
    for k, s in sens.items():
        print(f"  sensitivity {k}: {s['verdict']}")
for b in blockers:
    print("  BLOCKER:", b)
print("  wrote B1_1_SCORING_REPORT.{json,md}")
print("  Verdict does NOT unblock Track B (no_rescue). Track B BLOCKED. Structure, not validated meaning.")
