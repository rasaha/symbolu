#!/usr/bin/env python3
"""metrics_report.py — raw ablation artifacts -> summary json + table + verdict (Task 5/8).

Reads a runs/cg_wrapper_ablation/<timestamp>/ directory (per_example_scores.jsonl,
diagnostics.jsonl, config.json), computes per-arm objective rates, paired stats (McNemar +
bootstrap, B vs A), aggregates the logit/correction diagnostics, and applies the PRE-REGISTERED
kill criteria (K0/K1/K2/K3/K4) from RESEARCH_PLAN.md. Pure Python — no torch — so it can be
unit-tested and run anywhere.

Usage:
    python scripts/cg_wrapper_ablation/metrics_report.py runs/cg_wrapper_ablation/<timestamp>
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cg_ablation import metrics as M  # noqa: E402

# Pre-registered thresholds (RESEARCH_PLAN.md §6).
K0_MAX_LOGIT_DIFF = 1e-4
K1_KL = 1e-3
K1_FLIP = 5e-3
K1_RATIO = 1e-2
ALPHA = 0.05


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def build_summary(run_dir: Path) -> Dict[str, Any]:
    config = json.loads((run_dir / "config.json").read_text()) if (run_dir / "config.json").exists() else {}
    scores = _read_jsonl(run_dir / "per_example_scores.jsonl")
    diags = _read_jsonl(run_dir / "diagnostics.jsonl")

    # --- per-arm task rates + paired alignment by (set, id) -------------------
    # ok_by[(arm, set)][id] = bool   (seed-0 deterministic exact-match/constraint/json)
    ok_by: Dict[Any, Dict[str, bool]] = defaultdict(dict)
    agree_by: Dict[Any, List[float]] = defaultdict(list)
    arms = set()
    sets = set()
    for r in scores:
        arms.add(r["arm"])
        sets.add(r["set"])
        if r.get("metric") == "seed_agreement":
            agree_by[(r["arm"], r["set"])].append(r["value"])
        elif "ok" in r:
            ok_by[(r["arm"], r["set"])][r["id"]] = bool(r["ok"])

    arms = sorted(arms)
    sets = sorted(sets)

    per_arm: Dict[str, Any] = {}
    for arm in arms:
        per_set = {}
        for s in sets:
            vals = list(ok_by[(arm, s)].values())
            rate = M.summarize_rate(vals)
            rate["seed_agreement_mean"] = _mean(agree_by[(arm, s)])
            per_set[s] = rate
        per_arm[arm] = per_set

    # --- paired B vs A stats per set ------------------------------------------
    paired: Dict[str, Any] = {}
    if "A_base" in arms and "B_full" in arms:
        for s in sets:
            a_map = ok_by[("A_base", s)]
            b_map = ok_by[("B_full", s)]
            ids = sorted(set(a_map) & set(b_map))
            a = [a_map[i] for i in ids]
            b = [b_map[i] for i in ids]
            if not ids:
                continue
            mc = M.mcnemar_exact(a, b)
            pt, lo, hi = M.paired_bootstrap_ci([float(x) for x in a], [float(x) for x in b])
            paired[s] = {
                "n": len(ids),
                "rate_A": _mean([float(x) for x in a]),
                "rate_B": _mean([float(x) for x in b]),
                "mcnemar": mc,
                "bootstrap_delta": {"point": pt, "lo": lo, "hi": hi},
                "significant": (mc["p_value"] < ALPHA) and (lo > 0 or hi < 0),
                "direction": "improve" if pt > 0 else ("regress" if pt < 0 else "none"),
            }

    # --- diagnostics aggregation per arm --------------------------------------
    diag_by_arm: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in diags:
        diag_by_arm[d["arm"]].append(d)
    diag_summary: Dict[str, Any] = {}
    for arm, ds in diag_by_arm.items():
        diag_summary[arm] = {
            "mean_logit_kl_vs_base": _mean(d["logit_kl_vs_base"] for d in ds),
            "mean_top1_flip_vs_base": _mean(d["top1_flip_rate_vs_base"] for d in ds),
            "mean_adapter_gate": _mean(d["adapter_gate"] for d in ds),
            "mean_adapter_output_norm": _mean(d["adapter_output_norm"] for d in ds),
            "mean_correction_to_hidden_ratio": _mean(d["correction_to_hidden_ratio"] for d in ds),
            "mean_delta_bhava_norm": _mean(d.get("delta_bhava_norm", 0.0) for d in ds),
            "max_abs_logit_diff_vs_base": max((d.get("max_abs_logit_diff_vs_base", 0.0) for d in ds), default=0.0),
        }

    verdict = evaluate_kill_criteria(per_arm, paired, diag_summary)

    return {
        "config": config,
        "arms": arms,
        "sets": sets,
        "per_arm_rates": per_arm,
        "paired_B_vs_A": paired,
        "diagnostics": diag_summary,
        "verdict": verdict,
    }


def evaluate_kill_criteria(per_arm, paired, diag_summary) -> Dict[str, Any]:
    """Apply K0..K4 in order. Returns a structured verdict with the triggering numbers."""
    out: Dict[str, Any] = {"checks": {}}

    # K0 — gate0 (arm D) must equal base.
    d_diag = diag_summary.get("D_gate0", {})
    k0_diff = d_diag.get("max_abs_logit_diff_vs_base", 0.0)
    k0_ok = k0_diff <= K0_MAX_LOGIT_DIFF
    out["checks"]["K0_gate0_equals_base"] = {
        "max_abs_logit_diff": k0_diff, "threshold": K0_MAX_LOGIT_DIFF,
        "pass": k0_ok,
        "note": "OK" if k0_ok else "HIDDEN COUPLING: gate=0 is not logit-identical to base",
    }

    # K1 — inert? (arm B vs base)
    b = diag_summary.get("B_full", {})
    kl = b.get("mean_logit_kl_vs_base", 0.0)
    flip = b.get("mean_top1_flip_vs_base", 0.0)
    ratio = b.get("mean_correction_to_hidden_ratio", 0.0)
    inert = (kl < K1_KL) and (flip < K1_FLIP) and (ratio < K1_RATIO)
    out["checks"]["K1_inert"] = {
        "mean_logit_kl": kl, "mean_top1_flip": flip, "mean_corr_hidden_ratio": ratio,
        "thresholds": {"kl": K1_KL, "flip": K1_FLIP, "ratio": K1_RATIO},
        "inert": inert,
    }

    # K3 — regression on any task metric (significant negative).
    regressions = [s for s, p in paired.items()
                   if p.get("significant") and p.get("direction") == "regress"]
    # K4 — benefit on some metric (significant positive), and no regression.
    benefits = [s for s, p in paired.items()
                if p.get("significant") and p.get("direction") == "improve"]
    # K2 — not inert but no significant movement anywhere.
    any_significant = bool(regressions or benefits)

    if not out["checks"]["K0_gate0_equals_base"]["pass"]:
        decision = "INVESTIGATE_K0_HIDDEN_COUPLING"
    elif inert:
        decision = "INERT_STOP"            # K1
    elif regressions:
        decision = "KILL_OR_RETRAIN"       # K3
    elif benefits:
        decision = "BENEFIT_RECORDED"      # K4
    elif not any_significant:
        decision = "NO_EFFECT_DEPRIORITIZE"  # K2
    else:
        decision = "UNCLEAR_REVIEW"

    out["decision"] = decision
    out["benefit_sets"] = benefits
    out["regression_sets"] = regressions
    return out


def print_table(summary: Dict[str, Any]) -> None:
    print("\n================ CG WRAPPER ABLATION — SUMMARY ================")
    cfg = summary.get("config", {})
    print(f"model={cfg.get('model_id')}  ckpt={cfg.get('checkpoint')}  dtype={cfg.get('dtype')}")
    print(f"arms={summary['arms']}  sets={summary['sets']}\n")

    print(f"{'arm':<14}{'set':<20}{'n':>4}{'pass_rate':>11}{'seed_agree':>12}")
    for arm in summary["arms"]:
        for s in summary["sets"]:
            r = summary["per_arm_rates"][arm][s]
            print(f"{arm:<14}{s:<20}{r['n']:>4}{r['rate']:>11.3f}{r['seed_agreement_mean']:>12.3f}")

    print("\n-- paired B vs A (per set) --")
    for s, p in summary["paired_B_vs_A"].items():
        bd = p["bootstrap_delta"]
        print(f"  {s:<20} A={p['rate_A']:.3f} B={p['rate_B']:.3f} "
              f"Δ={bd['point']:+.3f} [{bd['lo']:+.3f},{bd['hi']:+.3f}] "
              f"McNemar p={p['mcnemar']['p_value']:.3g} "
              f"{'SIG' if p['significant'] else 'ns'} ({p['direction']})")

    print("\n-- diagnostics (vs base) --")
    for arm, d in summary["diagnostics"].items():
        print(f"  {arm:<14} KL={d['mean_logit_kl_vs_base']:.3e} "
              f"flip={d['mean_top1_flip_vs_base']:.3%} "
              f"gate={d['mean_adapter_gate']:.4f} "
              f"corr/hidden={d['mean_correction_to_hidden_ratio']:.3e}")

    v = summary["verdict"]
    print("\n-- kill criteria --")
    k0 = v["checks"]["K0_gate0_equals_base"]
    print(f"  K0 gate0==base : {'PASS' if k0['pass'] else 'FAIL'} (max|Δlogit|={k0['max_abs_logit_diff']:.3e})")
    k1 = v["checks"]["K1_inert"]
    print(f"  K1 inert       : {'YES' if k1['inert'] else 'no'} "
          f"(KL={k1['mean_logit_kl']:.3e}, flip={k1['mean_top1_flip']:.3%}, ratio={k1['mean_corr_hidden_ratio']:.3e})")
    print(f"\n  DECISION: {v['decision']}")
    if v["benefit_sets"]:
        print(f"    benefit on: {v['benefit_sets']}")
    if v["regression_sets"]:
        print(f"    regression on: {v['regression_sets']}")
    print("==============================================================\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: metrics_report.py <run_dir>")
        return 2
    run_dir = Path(sys.argv[1])
    if not run_dir.exists():
        print(f"run dir not found: {run_dir}")
        return 2
    summary = build_summary(run_dir)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print_table(summary)
    print(f"summary written to {run_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
