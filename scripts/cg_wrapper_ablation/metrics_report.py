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

    # --- paired stats per set, for any ordered arm pair (X is reference, Y is candidate) ----
    def _paired(x_arm: str, y_arm: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if x_arm not in arms or y_arm not in arms:
            return out
        for s in sets:
            x_map = ok_by[(x_arm, s)]
            y_map = ok_by[(y_arm, s)]
            ids = sorted(set(x_map) & set(y_map))
            if not ids:
                continue
            x = [x_map[i] for i in ids]
            y = [y_map[i] for i in ids]
            mc = M.mcnemar_exact(x, y)
            pt, lo, hi = M.paired_bootstrap_ci([float(v) for v in x], [float(v) for v in y])
            out[s] = {
                "n": len(ids),
                "rate_ref": _mean([float(v) for v in x]),
                "rate_cand": _mean([float(v) for v in y]),
                "mcnemar": mc,
                "bootstrap_delta": {"point": pt, "lo": lo, "hi": hi},  # cand - ref
                "significant": (mc["p_value"] < ALPHA) and (lo > 0 or hi < 0),
                "direction": "improve" if pt > 0 else ("regress" if pt < 0 else "none"),
            }
        return out

    # B vs A: does the (active) wrapper change objective metrics vs base.
    # B vs C: is there a phase/Bhava-DYNAMIC component beyond the static adapter offset.
    # C vs A: does even the static offset (phase signal zeroed) move metrics.
    paired = _paired("A_base", "B_full")          # rate_ref=A, rate_cand=B (kept name for back-compat)
    paired_b_vs_c = _paired("C_phase_off", "B_full")  # ref=C, cand=B  → B−C delta
    paired_c_vs_a = _paired("A_base", "C_phase_off")  # ref=A, cand=C  → C−A delta
    # Back-compat alias: old schema used rate_A/rate_B on the B-vs-A block.
    for s, p in paired.items():
        p["rate_A"], p["rate_B"] = p["rate_ref"], p["rate_cand"]

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
            "mean_adapter_weight_norm": _mean(d.get("adapter_weight_norm", 0.0) for d in ds),
            "max_abs_logit_diff_vs_base": max((d.get("max_abs_logit_diff_vs_base", 0.0) for d in ds), default=0.0),
        }

    # --- B-vs-C logit separation (phase ON vs phase OFF) ----------------------
    # Captured per example in diagnostics.jsonl under arm "B_vs_C" (run_ablation logs it).
    # If KL(B||C) ~ 0 and flip ~ 0, the phase/Bhava dynamics add ~nothing beyond the static
    # offset that C already carries — the wrapper effect is a constant, not CG-dynamic.
    bc = diag_by_arm.get("B_vs_C", [])
    b_vs_c_logit = {
        "mean_logit_kl_B_vs_C": _mean(d.get("logit_kl_vs_base", 0.0) for d in bc),
        "mean_top1_flip_B_vs_C": _mean(d.get("top1_flip_rate_vs_base", 0.0) for d in bc),
        "n": len(bc),
    }

    verdict = evaluate_kill_criteria(
        per_arm, paired, diag_summary,
        paired_b_vs_c=paired_b_vs_c, paired_c_vs_a=paired_c_vs_a, b_vs_c_logit=b_vs_c_logit,
    )

    return {
        "config": config,
        "arms": arms,
        "sets": sets,
        "per_arm_rates": per_arm,
        "paired_B_vs_A": paired,
        "paired_B_vs_C": paired_b_vs_c,
        "paired_C_vs_A": paired_c_vs_a,
        "b_vs_c_logit_separation": b_vs_c_logit,
        "diagnostics": diag_summary,
        "verdict": verdict,
    }


def evaluate_kill_criteria(per_arm, paired, diag_summary,
                           paired_b_vs_c=None, paired_c_vs_a=None,
                           b_vs_c_logit=None) -> Dict[str, Any]:
    """Apply the pre-registered checks and return a structured verdict.

    Decision categories (RESEARCH_PLAN.md §6, post Active-CG):
      INVESTIGATE_K0_HIDDEN_COUPLING — gate=0 (arm D) != base.
      INERT                          — wrapper changes ~nothing (K1).
      REGRESSION                     — B significantly worse than A on a task metric.
      CG_DYNAMIC_SIGNAL              — B>A AND B>C (the gain needs the phase/Bhava dynamics).
      STATIC_OFFSET_NO_CG_DYNAMIC    — B moves metrics vs A but B≈C (effect is the constant
                                       adapter offset, not CG dynamics).
      WEAK_OBJECTIVE_GAIN            — B>A on something, but the B-vs-C picture is ambiguous.
      ACTIVE_NO_EFFECT               — active (not inert) but no significant task movement.
    """
    paired_b_vs_c = paired_b_vs_c or {}
    paired_c_vs_a = paired_c_vs_a or {}
    b_vs_c_logit = b_vs_c_logit or {}
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

    # Task-metric movement (significance = McNemar p<α AND bootstrap CI excludes 0).
    b_improves_A = [s for s, p in paired.items()
                    if p.get("significant") and p.get("direction") == "improve"]
    b_regresses_A = [s for s, p in paired.items()
                     if p.get("significant") and p.get("direction") == "regress"]
    b_improves_C = [s for s, p in paired_b_vs_c.items()
                    if p.get("significant") and p.get("direction") == "improve"]
    b_vs_c_distinguishable = [s for s, p in paired_b_vs_c.items() if p.get("significant")]
    c_moves_A = [s for s, p in paired_c_vs_a.items() if p.get("significant")]

    # Logit-level B-vs-C separation (is the phase signal doing anything to logits at all).
    bc_kl = b_vs_c_logit.get("mean_logit_kl_B_vs_C", 0.0)
    bc_flip = b_vs_c_logit.get("mean_top1_flip_B_vs_C", 0.0)
    b_equiv_c_logits = (bc_kl < K1_KL) and (bc_flip < K1_FLIP)

    out["checks"]["B_vs_C_separation"] = {
        "mean_logit_kl_B_vs_C": bc_kl, "mean_top1_flip_B_vs_C": bc_flip,
        "task_distinguishable_sets": b_vs_c_distinguishable,
        "b_equivalent_to_c": (not b_vs_c_distinguishable) and b_equiv_c_logits,
        "note": ("B≈C: phase/Bhava dynamics add ~nothing beyond the static offset"
                 if (not b_vs_c_distinguishable) and b_equiv_c_logits
                 else "B and C are distinguishable (phase signal has a measurable effect)"),
    }

    # --- decision tree (ordered) ---------------------------------------------
    if not k0_ok:
        decision = "INVESTIGATE_K0_HIDDEN_COUPLING"
    elif inert:
        decision = "INERT"
    elif b_regresses_A:
        decision = "REGRESSION"
    elif b_improves_A and b_improves_C:
        decision = "CG_DYNAMIC_SIGNAL"          # gain that needs the dynamics
    elif b_improves_A and not b_vs_c_distinguishable:
        decision = "STATIC_OFFSET_NO_CG_DYNAMIC"  # gain, but it's the constant offset
    elif b_improves_A:
        decision = "WEAK_OBJECTIVE_GAIN"         # gain vs A, B-vs-C ambiguous
    elif c_moves_A and not b_vs_c_distinguishable:
        decision = "STATIC_OFFSET_NO_CG_DYNAMIC"  # active & moves metrics via static offset
    else:
        decision = "ACTIVE_NO_EFFECT"

    out["decision"] = decision
    out["b_improves_A_sets"] = b_improves_A
    out["b_regresses_A_sets"] = b_regresses_A
    out["b_improves_C_sets"] = b_improves_C
    out["c_moves_A_sets"] = c_moves_A
    # Warnings the user asked to surface explicitly.
    out["warnings"] = []
    if decision == "STATIC_OFFSET_NO_CG_DYNAMIC":
        out["warnings"].append(
            "STATIC OFFSET: B and C are not distinguishable but the wrapper differs from base — "
            "the effect is a constant adapter offset, NOT phase/Bhava dynamics.")
    if b_regresses_A:
        out["warnings"].append(
            f"REGRESSION: B significantly worse than A on {b_regresses_A} (format/reasoning/constraint).")
    if inert:
        out["warnings"].append("INERT: wrapper changes essentially nothing (check the checkpoint is trained/active).")
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

    def _paired_block(title, blk):
        if not blk:
            return
        print(f"\n-- {title} (per set; Δ = cand − ref) --")
        for s, p in blk.items():
            bd = p["bootstrap_delta"]
            print(f"  {s:<20} ref={p['rate_ref']:.3f} cand={p['rate_cand']:.3f} "
                  f"Δ={bd['point']:+.3f} [{bd['lo']:+.3f},{bd['hi']:+.3f}] "
                  f"McNemar p={p['mcnemar']['p_value']:.3g} "
                  f"{'SIG' if p['significant'] else 'ns'} ({p['direction']})")

    _paired_block("paired B vs C  (ref=C phase-off, cand=B full)  → is the effect CG-DYNAMIC?",
                  summary.get("paired_B_vs_C"))
    _paired_block("paired C vs A  (ref=A base, cand=C phase-off)  → static-offset size",
                  summary.get("paired_C_vs_A"))

    sep = summary.get("b_vs_c_logit_separation", {})
    if sep:
        print(f"\n-- B vs C logit separation --  KL(B||C)={sep.get('mean_logit_kl_B_vs_C',0):.3e} "
              f"flip={sep.get('mean_top1_flip_B_vs_C',0):.3%} (n={sep.get('n',0)})")

    print("\n-- diagnostics (vs base) --")
    for arm, d in summary["diagnostics"].items():
        print(f"  {arm:<14} KL={d['mean_logit_kl_vs_base']:.3e} "
              f"flip={d['mean_top1_flip_vs_base']:.3%} "
              f"gate={d['mean_adapter_gate']:.4f} "
              f"corr/hidden={d['mean_correction_to_hidden_ratio']:.3e} "
              f"ΔBhava={d.get('mean_delta_bhava_norm',0):.3e} "
              f"adptW={d.get('mean_adapter_weight_norm',0):.3e}")

    v = summary["verdict"]
    print("\n-- checks --")
    k0 = v["checks"]["K0_gate0_equals_base"]
    print(f"  K0 gate0==base : {'PASS' if k0['pass'] else 'FAIL'} (max|Δlogit|={k0['max_abs_logit_diff']:.3e})")
    k1 = v["checks"]["K1_inert"]
    print(f"  K1 inert       : {'YES' if k1['inert'] else 'no'} "
          f"(KL={k1['mean_logit_kl']:.3e}, flip={k1['mean_top1_flip']:.3%}, ratio={k1['mean_corr_hidden_ratio']:.3e})")
    bc = v["checks"].get("B_vs_C_separation", {})
    if bc:
        print(f"  B≈C            : {'YES' if bc.get('b_equivalent_to_c') else 'no'}  — {bc.get('note','')}")
    print(f"\n  DECISION: {v['decision']}")
    for key, label in [("b_improves_A_sets", "B>A improve"), ("b_improves_C_sets", "B>C improve"),
                       ("b_regresses_A_sets", "B<A regress"), ("c_moves_A_sets", "C≠A moves")]:
        if v.get(key):
            print(f"    {label}: {v[key]}")
    for w in v.get("warnings", []):
        print(f"    ⚠ {w}")
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
