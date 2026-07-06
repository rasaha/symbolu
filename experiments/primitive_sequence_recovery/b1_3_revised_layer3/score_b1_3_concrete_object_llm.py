#!/usr/bin/env python3
"""Scorer for the B1.3 concrete-object LLM judged-modulation study (scoring contract V2).

PRE-FREEZE implementation. Deterministic; NO network; NO judge calls. Scores a judge-output JSONL against the
frozen stimuli and emits exactly ONE terminal decision label plus a full report. Intended to be run ONLY on
real judge outputs AFTER an explicit EVIDENCE_FREEZE, or on synthetic fixtures for testing.

Structure, not validated meaning. This script does not itself earn any label; it computes one from data.

Terminal labels:
  LLM_OBJECT_MODULATION_SIGNAL_EARNED_STRONG
  LLM_OBJECT_MODULATION_SIGNAL_EARNED_CATEGORY_LIMITED
  LLM_OBJECT_MODULATION_NULL
  LLM_OBJECT_MODULATION_STYLE_CONFOUNDED
  LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS
  LLM_OBJECT_MODULATION_INVALID_RUN
"""
import argparse, json, math, hashlib, sys
from collections import defaultdict, Counter

# ------------------------------------------------------------------ constants
REQUIRED_COMPARISONS = [
    "A_real_vs_R_deranged_mid",
    "A_real_vs_R_deranged_far",
    "A_real_vs_R_deranged_near",
    "A_real_vs_R_scrambled",
    "A_real_vs_R_random",
    "A_real_vs_X_neutral",
    "A_real_vs_semantic_only_baseline",
]
PRIMARY_COMPARISON = "A_real_vs_R_deranged_mid"
DIRECTIONAL_CONTROLS = ["A_real_vs_R_scrambled", "A_real_vs_R_random", "A_real_vs_X_neutral"]
CI_LOWER_CONTROLS = ["A_real_vs_R_deranged_mid", "A_real_vs_R_deranged_far"]
BASELINE_COMPARISON = "A_real_vs_semantic_only_baseline"
NEAR_COMPARISON = "A_real_vs_R_deranged_near"
INVALID_RATE_CAP = 0.10
CI_LOWER_THRESHOLD = 0.50
DIRECTIONAL_THRESHOLD = 0.50
MODEL_FAMILY_DOMINANCE_FRAC = 0.60   # no single model family may drive > this share of A_real wins
REQUIRED_JUDGE_FIELDS = ["item_id", "comparison_id", "arm_left", "arm_right", "selected_option"]

TERMINAL_LABELS = {
    "STRONG": "LLM_OBJECT_MODULATION_SIGNAL_EARNED_STRONG",
    "CATEGORY_LIMITED": "LLM_OBJECT_MODULATION_SIGNAL_EARNED_CATEGORY_LIMITED",
    "NULL": "LLM_OBJECT_MODULATION_NULL",
    "STYLE_CONFOUNDED": "LLM_OBJECT_MODULATION_STYLE_CONFOUNDED",
    "SEMANTIC_BASELINE_EXPLAINS": "LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS",
    "INVALID_RUN": "LLM_OBJECT_MODULATION_INVALID_RUN",
}

# ------------------------------------------------------------------ helpers
def sha256_file(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError:
        return None

def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def wilson_interval(wins, n, z=1.959963984540054):
    """Wilson score interval for a binomial proportion (deterministic). Returns (lo, hi, phat)."""
    if n == 0:
        return (0.0, 1.0, float("nan"))
    phat = wins / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half), phat)

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def two_sided_binom_p_normal(wins, n, p0=0.5):
    """Deterministic normal-approx two-sided p-value for H0: p = 0.5 (used for Holm ordering).
    Exact Clopper-Pearson is used for the CI decision; this p is a reporting/ordering aid."""
    if n == 0:
        return 1.0
    phat = wins / n
    se = math.sqrt(p0 * (1 - p0) / n)
    if se == 0:
        return 1.0
    z = (phat - p0) / se
    return max(0.0, min(1.0, 2 * (1 - norm_cdf(abs(z)))))

def holm(pvals):
    """Holm-Bonferroni. Input {key: p}. Returns {key: adjusted_p}."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj = {}
    running = 0.0
    for i, (k, p) in enumerate(items):
        a = min(1.0, (m - i) * p)
        running = max(running, a)  # enforce monotonicity
        adj[k] = running
    return adj

# ------------------------------------------------------------------ selection -> A_real win
def selected_side(sel):
    """Map a selected_option to 'left'/'right' or None if invalid."""
    if sel is None:
        return None
    s = str(sel).strip().lower()
    if s in ("a", "left", "l", "option_a", "option a"):
        return "left"
    if s in ("b", "right", "r", "option_b", "option b"):
        return "right"
    return None

def judgment_outcome(row):
    """Return ('valid', a_real_won: bool) or ('invalid', reason)."""
    for f in REQUIRED_JUDGE_FIELDS:
        if f not in row:
            return ("invalid", f"missing_field:{f}")
    if row.get("invalid_flag") is True:
        return ("invalid", "invalid_flag")
    ps = str(row.get("parse_status", "ok")).lower()
    if ps in ("unparseable", "refused", "malformed", "tie"):
        return ("invalid", f"parse_status:{ps}")
    side = selected_side(row.get("selected_option"))
    if side is None:
        return ("invalid", "unmappable_selection")
    won_arm = row["arm_left"] if side == "left" else row["arm_right"]
    other = row["arm_right"] if side == "left" else row["arm_left"]
    if "A_real" not in (row["arm_left"], row["arm_right"]):
        return ("invalid", "no_A_real_arm_in_pair")
    a_real_won = (won_arm == "A_real")
    return ("valid", a_real_won)

# ------------------------------------------------------------------ core scoring
def score(stimuli_path, judge_path, style_audit_path, contract_path, out_json, out_md):
    warnings = []
    inputs = {
        "stimuli": {"path": stimuli_path, "sha256": sha256_file(stimuli_path)},
        "judge_outputs": {"path": judge_path, "sha256": sha256_file(judge_path)},
        "style_audit_report": {"path": style_audit_path, "sha256": sha256_file(style_audit_path)},
        "scoring_contract": {"path": contract_path, "sha256": sha256_file(contract_path)},
    }
    judge_rows = read_jsonl(judge_path)
    style_audit = json.loads(open(style_audit_path, encoding="utf-8").read()) if style_audit_path else {}

    # --- audit gate (pre-scoring): STYLE_CONFOUNDED if any pre-judge audit did not pass
    audit_pass = _audits_passed(style_audit)
    audit_summary = _audit_summary(style_audit)

    # --- tally per comparison (primary tier only for the endpoint set)
    per_comp = {c: {"wins": 0, "n": 0} for c in REQUIRED_COMPARISONS}
    per_comp_by_family = defaultdict(lambda: defaultdict(lambda: {"wins": 0, "n": 0}))
    per_comp_by_model = defaultdict(lambda: defaultdict(lambda: {"wins": 0, "n": 0}))
    a_real_wins_by_model = Counter()
    a_real_total_by_model = Counter()
    secondary_diag = {"secondary": {"wins": 0, "n": 0}, "diagnostic": {"wins": 0, "n": 0}}
    invalid = Counter()
    n_total = 0
    tiers_seen = Counter()

    for row in judge_rows:
        n_total += 1
        tier = row.get("primary_or_secondary_or_diagnostic", "primary")
        tiers_seen[tier] += 1
        status, info = judgment_outcome(row)
        comp = row.get("comparison_id")
        if status == "invalid":
            invalid[info] += 1
            continue
        a_won = info
        if tier != "primary":
            b = secondary_diag.get(tier)
            if b is not None:
                b["n"] += 1; b["wins"] += int(a_won)
            continue
        if comp not in per_comp:
            warnings.append(f"unknown_comparison_id:{comp}")
            continue
        per_comp[comp]["n"] += 1
        per_comp[comp]["wins"] += int(a_won)
        fam = row.get("object_family", "unknown")
        per_comp_by_family[comp][fam]["n"] += 1
        per_comp_by_family[comp][fam]["wins"] += int(a_won)
        mid = row.get("model_id", "unknown")
        per_comp_by_model[comp][mid]["n"] += 1
        per_comp_by_model[comp][mid]["wins"] += int(a_won)
        a_real_total_by_model[mid] += 1
        a_real_wins_by_model[mid] += int(a_won)

    n_valid = sum(v["n"] for v in per_comp.values()) + sum(b["n"] for b in secondary_diag.values())
    n_invalid = sum(invalid.values())
    invalid_rate = (n_invalid / n_total) if n_total else 1.0

    # --- comparison results with CIs and p-values
    comparison_results = {}
    pvals = {}
    for c in REQUIRED_COMPARISONS:
        w, n = per_comp[c]["wins"], per_comp[c]["n"]
        lo, hi, phat = wilson_interval(w, n)
        cp_lo, cp_hi = clopper_pearson(w, n)
        p = two_sided_binom_p_normal(w, n)
        pvals[c] = p
        comparison_results[c] = {
            "wins": w, "n": n, "win_rate": None if n == 0 else round(phat, 4),
            "wilson_ci": [round(lo, 4), round(hi, 4)],
            "clopper_pearson_ci": [round(cp_lo, 4), round(cp_hi, 4)],
            "p_value_normal_approx": round(p, 6),
        }
    holm_adj = holm(pvals)
    for c in REQUIRED_COMPARISONS:
        comparison_results[c]["p_holm_adjusted"] = round(holm_adj[c], 6)

    # --- near/mid/far gradient
    def wr(c):
        n = per_comp[c]["n"]
        return None if n == 0 else per_comp[c]["wins"] / n
    gradient = {
        "near_win_rate": None if wr(NEAR_COMPARISON) is None else round(wr(NEAR_COMPARISON), 4),
        "mid_win_rate": None if wr(PRIMARY_COMPARISON) is None else round(wr(PRIMARY_COMPARISON), 4),
        "far_win_rate": None if wr("A_real_vs_R_deranged_far") is None else round(wr("A_real_vs_R_deranged_far"), 4),
    }
    gradient["monotone_far_ge_mid_ge_near"] = _monotone(gradient)

    # --- model-family breakdown + dominance check
    model_family_breakdown = {}
    for mid in sorted(a_real_total_by_model):
        tot = a_real_total_by_model[mid]
        model_family_breakdown[mid] = {
            "a_real_wins": a_real_wins_by_model[mid], "a_real_judgments": tot,
            "a_real_win_rate": None if tot == 0 else round(a_real_wins_by_model[mid] / tot, 4),
        }
    total_a_wins = sum(a_real_wins_by_model.values())
    single_family_dominates = False
    dominant_family = None
    if total_a_wins > 0:
        for mid, w in a_real_wins_by_model.items():
            if w / total_a_wins > MODEL_FAMILY_DOMINANCE_FRAC and len(a_real_wins_by_model) > 1:
                single_family_dominates = True; dominant_family = mid
    # --- item-family breakdown (primary win rate by object family, on the primary comparison)
    item_family_breakdown = {}
    for fam, d in sorted(per_comp_by_family[PRIMARY_COMPARISON].items()):
        n = d["n"]
        item_family_breakdown[fam] = {"wins": d["wins"], "n": n,
                                      "win_rate": None if n == 0 else round(d["wins"] / n, 4)}

    # --- threshold evaluation
    thr = _threshold_eval(comparison_results, single_family_dominates)

    # --- terminal decision
    terminal_key, decision_reasons = _decide(
        audit_pass=audit_pass, invalid_rate=invalid_rate, per_comp=per_comp,
        comparison_results=comparison_results, thr=thr, single_family_dominates=single_family_dominates,
        n_total=n_total,
    )
    terminal_label = TERMINAL_LABELS[terminal_key]

    report = {
        "artifact": "b1_3_concrete_object_llm_scoring_report",
        "status": "SCORED", "evidence_freeze_declared": False,
        "terminal_label": terminal_label,
        "decision_reasons": decision_reasons,
        "primary_endpoint": {
            "comparison": PRIMARY_COMPARISON,
            "result": comparison_results[PRIMARY_COMPARISON],
            "threshold": f"lower CI bound > {CI_LOWER_THRESHOLD}",
            "passes": thr["ci_lower"][PRIMARY_COMPARISON],
        },
        "comparison_results": comparison_results,
        "near_mid_far_gradient": gradient,
        "model_family_breakdown": model_family_breakdown,
        "single_model_family_dominates": single_family_dominates,
        "dominant_model_family": dominant_family,
        "item_family_breakdown": item_family_breakdown,
        "secondary_diagnostic_results": _tier_results(secondary_diag),
        "invalid_summary": {
            "n_total_judgments": n_total, "n_valid": n_valid, "n_invalid": n_invalid,
            "invalid_rate": round(invalid_rate, 4), "invalid_rate_cap": INVALID_RATE_CAP,
            "invalid_breakdown": dict(invalid), "tiers_seen": dict(tiers_seen),
        },
        "audit_summary": audit_summary,
        "threshold_summary": thr,
        "warnings": warnings,
        "inputs": inputs,
        "prior_results_preserved": {
            "B1.1": "LLM null (RANDOM_OR_SCRAMBLED_MATCHES)", "B1.2_B1.3_automated": "nulls (scrambled~real 0.967)",
            "B1.3_register_field": "CLOSED", "B1.4_vritti": "CLOSED",
            "Track_G": "RANDOM_POLARITY_EXPLAINS (1fe5562)", "Track_F": "CORRECTNESS_DEGRADED", "Track_B": "BLOCKED",
        },
        "disallowed_labels": ["HUMAN_PROPENSITY_MODULATION_SIGNAL", "PROPENSITY_MODULATION_SIGNAL",
            "LIMITED_GENERATION_UTILITY", "MAPPING_FIDELITY_SIGNAL", "ontology_validation",
            "Sanskrit_privilege", "semantic_truth"],
        "anchors": {"b1_1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b": "BLOCKED", "evidence_freeze": "NONE"},
        "non_claims": ["scorer output; not a validated meaning claim", "structure, not validated meaning"],
    }
    if out_json:
        open(out_json, "w", encoding="utf-8").write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if out_md:
        open(out_md, "w", encoding="utf-8").write(_render_md(report))
    return report

def clopper_pearson(wins, n, alpha=0.05):
    """Exact Clopper-Pearson interval via the Beta quantile (deterministic bisection on the Beta CDF)."""
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0 if wins == 0 else _beta_ppf(alpha / 2, wins, n - wins + 1)
    hi = 1.0 if wins == n else _beta_ppf(1 - alpha / 2, wins + 1, n - wins)
    return (lo, hi)

def _beta_cdf(x, a, b):
    """Regularized incomplete beta I_x(a,b) via continued fraction (Lentz), deterministic."""
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a
    # Lentz continued fraction
    f, c, d = 1.0, 1.0, 0.0
    tiny = 1e-30
    for i in range(0, 400):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2*m - 1) * (a + 2*m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2*m) * (a + 2*m + 1))
        d = 1.0 + num * d
        if abs(d) < tiny: d = tiny
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < tiny: c = tiny
        delta = c * d
        f *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return min(1.0, max(0.0, front * (f - 1.0)))

def _beta_ppf(p, a, b):
    """Inverse Beta CDF by bisection (deterministic)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _beta_cdf(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

# ------------------------------------------------------------------ sub-helpers
def _audits_passed(style_audit):
    if not style_audit:
        return False
    keys = ["style_parity_audit", "style_tell_audit", "denotation_leakage_audit",
            "quality_parity_audit", "semantic_baseline_audit"]
    for k in keys:
        sub = style_audit.get(k)
        if not isinstance(sub, dict) or sub.get("pass") is not True:
            return False
    return style_audit.get("overall_audit_pass", False) is True

def _audit_summary(style_audit):
    keys = ["style_parity_audit", "style_tell_audit", "denotation_leakage_audit",
            "quality_parity_audit", "semantic_baseline_audit"]
    out = {k: (style_audit.get(k, {}).get("pass") if isinstance(style_audit.get(k), dict) else None) for k in keys}
    out["overall_audit_pass"] = style_audit.get("overall_audit_pass")
    out["style_tell_balanced_accuracy"] = style_audit.get("style_tell_audit", {}).get("balanced_accuracy")
    return out

def _monotone(g):
    vals = [g["far_win_rate"], g["mid_win_rate"], g["near_win_rate"]]
    if any(v is None for v in vals):
        return None
    return vals[0] >= vals[1] >= vals[2]

def _tier_results(secondary_diag):
    out = {}
    for tier, d in secondary_diag.items():
        n = d["n"]
        out[tier] = {"wins": d["wins"], "n": n, "win_rate": None if n == 0 else round(d["wins"] / n, 4)}
    return out

def _threshold_eval(cr, single_family_dominates):
    ci_lower = {}
    for c in CI_LOWER_CONTROLS:
        ci_lower[c] = cr[c]["n"] > 0 and cr[c]["wilson_ci"][0] > CI_LOWER_THRESHOLD
    directional = {}
    for c in DIRECTIONAL_CONTROLS + [BASELINE_COMPARISON]:
        wr = cr[c]["win_rate"]
        directional[c] = wr is not None and wr > DIRECTIONAL_THRESHOLD
    baseline_not_beating = _baseline_not_matching(cr)
    near_wr = cr[NEAR_COMPARISON]["win_rate"]
    near_lo = cr[NEAR_COMPARISON]["wilson_ci"][0]
    return {
        "ci_lower": ci_lower,
        "directional": directional,
        "semantic_baseline_not_matching_or_beating": baseline_not_beating,
        "near_win_rate": near_wr, "near_ci_lower": near_lo,
        "near_beats_chance": (near_wr is not None and near_lo > CI_LOWER_THRESHOLD),
        "no_single_model_family_dominance": not single_family_dominates,
    }

def _baseline_not_matching(cr):
    """Baseline must NOT match or beat A_real: A_real must win the baseline comparison (> 0.5) directionally
    AND the baseline comparison lower CI must not fall at/under chance in a way that ties it."""
    b = cr[BASELINE_COMPARISON]
    if b["n"] == 0 or b["win_rate"] is None:
        return False
    return b["win_rate"] > DIRECTIONAL_THRESHOLD and b["wilson_ci"][0] > 0.45

def _decide(audit_pass, invalid_rate, per_comp, comparison_results, thr, single_family_dominates, n_total):
    reasons = []
    # 1. INVALID_RUN: broken / high invalid / missing comparisons
    missing = [c for c in REQUIRED_COMPARISONS if per_comp[c]["n"] == 0]
    if n_total == 0:
        return "INVALID_RUN", ["no judgments"]
    if missing:
        reasons.append(f"missing_required_comparisons:{missing}")
        return "INVALID_RUN", reasons
    if invalid_rate > INVALID_RATE_CAP:
        reasons.append(f"invalid_rate {round(invalid_rate,4)} > cap {INVALID_RATE_CAP}")
        return "INVALID_RUN", reasons
    # 2. STYLE_CONFOUNDED: audits did not pass before scoring
    if not audit_pass:
        reasons.append("pre-judge audits did not all pass")
        return "STYLE_CONFOUNDED", reasons
    # 3. SEMANTIC_BASELINE_EXPLAINS: baseline matches or beats A_real
    if not thr["semantic_baseline_not_matching_or_beating"]:
        reasons.append("semantic_only_baseline matches or beats A_real")
        return "SEMANTIC_BASELINE_EXPLAINS", reasons
    # 4. NULL: fails mid or far (CI lower) or any directional control/baseline
    if not thr["ci_lower"][PRIMARY_COMPARISON]:
        reasons.append("A_real fails mid (lower CI not > 0.50)")
        return "NULL", reasons
    if not thr["ci_lower"]["A_real_vs_R_deranged_far"]:
        reasons.append("A_real fails far (lower CI not > 0.50)")
        return "NULL", reasons
    for c in DIRECTIONAL_CONTROLS:
        if not thr["directional"][c]:
            reasons.append(f"A_real fails directional control {c}")
            return "NULL", reasons
    if single_family_dominates:
        reasons.append("single model family dominates A_real wins")
        return "NULL", reasons
    # 5. STRONG vs CATEGORY_LIMITED on near
    if thr["near_beats_chance"]:
        reasons.append("A_real beats near, mid, far + all controls + baseline")
        return "STRONG", reasons
    reasons.append("A_real beats mid, far + controls + baseline but NOT near -> category-limited (no word-specificity claim)")
    return "CATEGORY_LIMITED", reasons

def _render_md(r):
    L = []
    L.append("# B1.3 Concrete-Object LLM Judged-Modulation — Scoring Report\n")
    L.append(f"**Terminal label:** `{r['terminal_label']}`  \n")
    L.append(f"**Decision reasons:** {'; '.join(r['decision_reasons'])}\n")
    L.append("**EVIDENCE_FREEZE:** not declared · **prior nulls preserved.** Structure, not validated meaning.\n")
    pe = r["primary_endpoint"]
    L.append(f"\n## Primary endpoint — {pe['comparison']}\n")
    res = pe["result"]
    L.append(f"- win rate: {res['win_rate']}  (n={res['n']}); Wilson CI {res['wilson_ci']}; "
             f"Clopper-Pearson CI {res['clopper_pearson_ci']}; passes (lower CI > 0.50): **{pe['passes']}**\n")
    L.append("\n## Required comparisons\n")
    L.append("| comparison | win rate | n | Wilson CI | p (Holm) |\n|---|---|---|---|---|\n")
    for c in REQUIRED_COMPARISONS:
        cr = r["comparison_results"][c]
        L.append(f"| {c} | {cr['win_rate']} | {cr['n']} | {cr['wilson_ci']} | {cr['p_holm_adjusted']} |\n")
    g = r["near_mid_far_gradient"]
    L.append(f"\n## Near/mid/far gradient\nnear {g['near_win_rate']} · mid {g['mid_win_rate']} · far {g['far_win_rate']} "
             f"· monotone(far≥mid≥near): {g['monotone_far_ge_mid_ge_near']}\n")
    L.append(f"\n## Semantic baseline\nA_real vs semantic_only_baseline win rate "
             f"{r['comparison_results'][BASELINE_COMPARISON]['win_rate']} — "
             f"baseline not matching/beating A_real: {r['threshold_summary']['semantic_baseline_not_matching_or_beating']}\n")
    inv = r["invalid_summary"]
    L.append(f"\n## Invalid-rate summary\n{inv['n_invalid']}/{inv['n_total_judgments']} invalid "
             f"(rate {inv['invalid_rate']}, cap {inv['invalid_rate_cap']}); breakdown {inv['invalid_breakdown']}\n")
    L.append(f"\n## Audit summary\n{r['audit_summary']}\n")
    L.append("\n## Interpretation\n")
    L.append("- STRONG requires A_real to beat near, mid, far + scrambled/random/neutral + semantic baseline.\n")
    L.append("- CATEGORY_LIMITED = beats mid/far + controls/baseline but not near (no word-specificity claim).\n")
    L.append("- SEMANTIC_BASELINE_EXPLAINS = ordinary object semantics explain the result.\n")
    L.append("\n## Caveats / preserved prior results\n")
    L.append("Automated probes found real≈fake objects (scrambled≈real 0.967; deranged≈real); prior nulls "
             "(B1.1 LLM null; B1.2/B1.3 automated; register-field CLOSED; vṛtti CLOSED; Track G/F) stand. "
             "This scorer earns no label by itself; a positive is LLM object-fit only — not human validation, "
             "ontology, Sanskrit privilege, or semantic truth. Track B BLOCKED.\n")
    return "".join(L)

# ------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Score the B1.3 concrete-object LLM judged-modulation study.")
    ap.add_argument("--stimuli", required=True)
    ap.add_argument("--judge-outputs", required=True)
    ap.add_argument("--style-audit", required=True)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    a = ap.parse_args(argv)
    report = score(a.stimuli, a.judge_outputs, a.style_audit, a.contract, a.out_json, a.out_md)
    print(report["terminal_label"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
