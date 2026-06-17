"""
run_experiment.py — End-to-end harness: dataset -> oracle -> features -> configs
-> metrics -> significance -> artifacts.

Usage:
    python -m experiments.signal_gov.run_experiment --mode mock --dataset smoke
    python -m experiments.signal_gov.run_experiment --mode mock --dataset handbuilt
    python -m experiments.signal_gov.run_experiment --mode cached --features path/to/features.jsonl
    python -m experiments.signal_gov.run_experiment --mode real_cg --checkpoint <ckpt>   # needs torch

Artifacts written to --out (default: experiments/signal_gov/out/<mode>_<dataset>/):
    results.json          full machine-readable results + metadata
    metrics.csv           per-config metric table
    signal_importance.csv standalone AUROC per feature/signal
    roc_overlay.png       ROC curves for C1..C4
    catch_at_budget.png   catch-rate bars at 5/10/20% budgets
    experiment_report.md  human-readable report (with mode disclaimers)

This harness ships as a *reproducible scaffold + smoke test*. It does NOT claim the
hypothesis is proven; the `mock` mode uses synthetic features (see README).
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np

from experiments.signal_gov import __doc__ as _pkg_doc  # noqa: F401
from experiments.signal_gov.configs import CONFIG_ORDER, CONFIGS, score_configs
from experiments.signal_gov.dataset import Scenario, category_balance, load_dataset
from experiments.signal_gov.delong import delong_roc_test
from experiments.signal_gov.features import FeatureVector, build_extractor
from experiments.signal_gov.metrics import (
    BUDGETS_DEFAULT,
    bootstrap_ci,
    per_config_metrics,
    roc_auc,
    signal_importance,
)
from experiments.signal_gov.oracle import label as oracle_label
from experiments.signal_gov.oracle import verify_consistency
from experiments.signal_gov.plots import catch_at_budget_bar, roc_overlay

PKG_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_ROOT = PKG_DIR / "out"

RESULTS_SCHEMA_KEYS = (
    "meta", "dataset", "configs", "delong_c4_vs_c3", "ordering_ok", "signal_importance",
)


@dataclass
class ExperimentResult:
    results: Dict
    out_dir: Path


def _labels_from_oracle(scenarios: List[Scenario]) -> np.ndarray:
    """Use the rule-based oracle as the label source of truth (not authored fields)."""
    return np.array([oracle_label(s).unsafe_label for s in scenarios], dtype=int)


def _oriented_feature_columns(features: List[FeatureVector]) -> Dict[str, List[float]]:
    """Per-feature values oriented so higher = riskier (for standalone AUROC)."""
    return {
        "risk_norm": [f.risk_norm for f in features],
        "inv_text_confidence": [1.0 - f.text_confidence for f in features],
        "entropy": [f.entropy for f in features],
        "inv_coherence": [1.0 - f.coherence for f in features],
        "vritti_risk": [f.vritti_risk for f in features],
        "jepa_disagreement": [f.jepa_disagreement for f in features],
    }


def run(mode: str, dataset: str, out_dir: Path, *, seed: int = 1234,
        features_path: str | None = None, n_boot: int = 2000,
        make_plots: bool = True, checkpoint: str | None = None,
        real_cg_stub: bool = False, strict_signals: bool = False,
        tier: str = "consumer") -> ExperimentResult:
    scenarios = load_dataset(dataset)

    # Label integrity: authored labels must match the rule-based oracle.
    mismatches = verify_consistency(scenarios)
    if mismatches:
        ids = ", ".join(sid for sid, _ in mismatches)
        raise RuntimeError(f"oracle/authored label mismatch for: {ids}")

    labels = _labels_from_oracle(scenarios)

    extractor = build_extractor(mode, seed=seed, features_path=features_path,
                                checkpoint=checkpoint, use_stub=real_cg_stub,
                                strict_signals=strict_signals, tier=tier)
    features = extractor.extract_all(scenarios)

    scores_by_config = score_configs(scenarios, features)
    tiebreak = np.arange(len(scenarios), dtype=float)  # deterministic tie-break

    config_metrics: Dict[str, Dict] = {}
    aurocs: Dict[str, float] = {}
    catch_by_config: Dict[str, Dict[str, float]] = {}
    for name in CONFIG_ORDER:
        scores = scores_by_config[name]
        m = per_config_metrics(labels, scores, BUDGETS_DEFAULT)
        # deterministic catch@budget overrides (tie-broken) for plotting/report
        from experiments.signal_gov.metrics import catch_at_budget
        m["catch_at_budget"] = {
            f"{b:.2f}": catch_at_budget(labels, scores, b, tiebreak) for b in BUDGETS_DEFAULT
        }
        _, lo, hi = bootstrap_ci(labels, scores, roc_auc, n_boot=n_boot, seed=seed)
        m["auroc_ci95"] = [lo, hi]
        config_metrics[name] = m
        aurocs[name] = m["auroc"]
        catch_by_config[name] = m["catch_at_budget"]

    # Ablation ordering on AUROC (NaN-safe).
    ordered_aucs = [aurocs[n] for n in CONFIG_ORDER]
    ordering_ok = all(
        (b >= a - 1e-9)
        for a, b in zip(ordered_aucs, ordered_aucs[1:])
        if not (np.isnan(a) or np.isnan(b))
    )

    # DeLong: C4 vs C3 (the decisive comparison).
    c3, c4 = CONFIG_ORDER[2], CONFIG_ORDER[3]
    auc_c3, auc_c4, p_val = delong_roc_test(labels, scores_by_config[c3], scores_by_config[c4])
    delong_block = {
        "config_a": c4, "config_b": c3,
        "auc_c4": auc_c4, "auc_c3": auc_c3,
        "delta_auroc": auc_c4 - auc_c3, "p_value": p_val,
    }

    sig_imp = signal_importance(labels, _oriented_feature_columns(features))

    results = {
        "meta": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "dataset": dataset,
            "seed": seed,
            "n_bootstrap": n_boot,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "feature_provenance": features[0].provenance if features else None,
            "disclaimer": (
                "mock mode uses SYNTHETIC features and validates the harness only; "
                "scientific conclusions require real_cg features + the full balanced "
                "benchmark + a held-out split."
            ),
        },
        "dataset": {
            "n_total": len(scenarios),
            "n_positive": int(labels.sum()),
            "positive_rate": float(labels.mean()) if len(labels) else float("nan"),
            "category_balance": category_balance(scenarios),
            "scenario_ids": [s.scenario_id for s in scenarios],
        },
        "configs": config_metrics,
        "delong_c4_vs_c3": delong_block,
        "ordering_ok": bool(ordering_ok),
        "signal_importance": sig_imp,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_results_json(results, out_dir / "results.json")
    _write_metrics_csv(config_metrics, out_dir / "metrics.csv")
    _write_signal_importance_csv(sig_imp, out_dir / "signal_importance.csv")
    if make_plots:
        roc_overlay(labels, scores_by_config, aurocs, out_dir / "roc_overlay.png")
        catch_at_budget_bar(catch_by_config, out_dir / "catch_at_budget.png")
    _write_report(results, out_dir / "experiment_report.md")

    return ExperimentResult(results=results, out_dir=out_dir)


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_results_json(results: Dict, path: Path) -> None:
    path.write_text(json.dumps(results, indent=2, sort_keys=False), encoding="utf-8")


def _write_metrics_csv(config_metrics: Dict[str, Dict], path: Path) -> None:
    budgets = sorted(next(iter(config_metrics.values()))["catch_at_budget"].keys(), key=float)
    header = (["config", "auroc", "auroc_ci_lo", "auroc_ci_hi", "auprc",
               "n", "n_positive", "human_burden_to_catch_0.90", "over_block_at_0.10"]
              + [f"catch@{b}" for b in budgets])
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for name in CONFIG_ORDER:
            m = config_metrics[name]
            ci = m.get("auroc_ci95", [float("nan"), float("nan")])
            row = [name, f"{m['auroc']:.4f}", f"{ci[0]:.4f}", f"{ci[1]:.4f}",
                   f"{m['auprc']:.4f}", m["n"], m["n_positive"],
                   f"{m['human_burden_to_catch_0.90']:.4f}", f"{m['over_block_at_0.10']:.4f}"]
            row += [f"{m['catch_at_budget'][b]:.4f}" for b in budgets]
            w.writerow(row)


def _write_signal_importance_csv(sig_imp: Dict[str, float], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "standalone_auroc"])
        for k, v in sorted(sig_imp.items(), key=lambda kv: (np.isnan(kv[1]), -kv[1] if not np.isnan(kv[1]) else 0)):
            w.writerow([k, f"{v:.4f}"])


def _write_report(results: Dict, path: Path) -> None:
    meta = results["meta"]
    ds = results["dataset"]
    lines: List[str] = []
    lines.append("# Signal-Governance Experiment — Run Report")
    lines.append("")
    lines.append(f"- **Mode:** `{meta['mode']}`  ·  **Dataset:** `{meta['dataset']}`  "
                 f"·  **Seed:** {meta['seed']}")
    lines.append(f"- **Created (UTC):** {meta['created_utc']}")
    lines.append(f"- **N:** {ds['n_total']}  ·  **Unsafe:** {ds['n_positive']} "
                 f"({ds['positive_rate']*100:.0f}%)  ·  **Category balance:** {ds['category_balance']}")
    lines.append("")
    prov = str(meta.get("feature_provenance") or "")
    if meta["mode"] != "real_cg":
        lines.append("> ⚠️ **Not a result.** This run uses "
                     f"`{meta['mode']}` features. The `mock` mode is SYNTHETIC and validates "
                     "the harness only. Scientific conclusions require `real_cg` features, the "
                     "full balanced benchmark, and a held-out split.")
        lines.append("")
    elif "stub" in prov:
        lines.append("> ⚠️ **Plumbing validation, not evidence.** This `real_cg` run uses a "
                     "deterministic STUB 32-D state (`StubCGLLMAdapter`), not live model "
                     "inference. The internal-signal extraction path (sovereign_bridge → "
                     "entropy/vritti adapters → JEPA) executes end-to-end, but the state is a "
                     "FIXED fixture, so internal signals are constant across scenarios and "
                     "carry NO discriminative claim. AUROC(C4)==AUROC(C3) is expected here. "
                     "Evidence requires a real CG checkpoint + the full balanced benchmark + a "
                     "held-out split.")
        lines.append("")
    lines.append("## Ablation metrics")
    lines.append("")
    lines.append("| Config | AUROC | AUROC 95% CI | AUPRC | catch@5% | catch@10% | catch@20% | over-block@10% |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name in CONFIG_ORDER:
        m = results["configs"][name]
        ci = m.get("auroc_ci95", [float("nan"), float("nan")])
        cb = m["catch_at_budget"]
        lines.append(
            f"| {name} | {m['auroc']:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] | {m['auprc']:.3f} | "
            f"{cb['0.05']:.3f} | {cb['0.10']:.3f} | {cb['0.20']:.3f} | {m['over_block_at_0.10']:.3f} |"
        )
    lines.append("")
    lines.append(f"**Ablation ordering C4 ≥ C3 ≥ C2 ≥ C1 on AUROC:** "
                 f"{'PASS' if results['ordering_ok'] else 'FAIL'}")
    lines.append("")
    d = results["delong_c4_vs_c3"]
    lines.append("## C4 vs C3 (DeLong paired AUROC test)")
    lines.append("")
    lines.append(f"- AUROC(C4) = {d['auc_c4']:.3f}, AUROC(C3) = {d['auc_c3']:.3f}, "
                 f"Δ = {d['delta_auroc']:+.3f}")
    pv = d["p_value"]
    lines.append(f"- DeLong p-value = {'nan (too few samples per class)' if np.isnan(pv) else f'{pv:.4f}'}")
    lines.append("")
    lines.append("## Standalone signal importance (AUROC, oriented higher=riskier)")
    lines.append("")
    lines.append("| Feature | Standalone AUROC |")
    lines.append("|---|---|")
    for k, v in sorted(results["signal_importance"].items(),
                       key=lambda kv: (np.isnan(kv[1]), -(kv[1] if not np.isnan(kv[1]) else 0))):
        lines.append(f"| {k} | {v:.3f} |")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append("`results.json` · `metrics.csv` · `signal_importance.csv` · "
                 "`roc_overlay.png` · `catch_at_budget.png`")
    lines.append("")
    lines.append("See `experiments/signal_gov/README.md` for the pre-registered "
                 "success/failure criteria the *real* experiment is judged against.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Signal-governance experiment harness")
    p.add_argument("--mode", choices=["mock", "cached", "real_cg"], default="mock")
    p.add_argument("--dataset", default="smoke",
                   help="handbuilt | smoke | <external source name>")
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--features", default=None, help="path to cached features (.jsonl/.parquet)")
    p.add_argument("--checkpoint", default=None, help="CG checkpoint for real_cg mode")
    p.add_argument("--real-cg-stub", action="store_true",
                   help="real_cg via StubCGLLMAdapter (torch-free plumbing validation)")
    p.add_argument("--strict-signals", action="store_true",
                   help="real_cg: raise instead of fail-closed when a signal is missing")
    p.add_argument("--tier", default="consumer", help="governance tier for real_cg")
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--no-plots", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT_ROOT / f"{args.mode}_{args.dataset}"
    res = run(args.mode, args.dataset, out_dir, seed=args.seed,
              features_path=args.features, n_boot=args.n_boot,
              make_plots=not args.no_plots, checkpoint=args.checkpoint,
              real_cg_stub=args.real_cg_stub, strict_signals=args.strict_signals,
              tier=args.tier)
    r = res.results
    print(f"[signal_gov] mode={args.mode} dataset={args.dataset} "
          f"N={r['dataset']['n_total']} unsafe={r['dataset']['n_positive']}")
    for name in CONFIG_ORDER:
        m = r["configs"][name]
        print(f"  {name:32s} AUROC={m['auroc']:.3f}  catch@10%={m['catch_at_budget']['0.10']:.3f}")
    print(f"  ordering C4>=C3>=C2>=C1: {'PASS' if r['ordering_ok'] else 'FAIL'}")
    print(f"  artifacts -> {res.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
