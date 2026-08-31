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
import logging
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np

from experiments.signal_gov import __doc__ as _pkg_doc  # noqa: F401
from experiments.signal_gov.configs import (
    CONFIG_ORDER, CONFIGS, VARIANT_CONFIG_ORDER, VARIANT_CONFIGS,
    score_configs, score_variant_configs,
)
from experiments.signal_gov.dataset import (
    Scenario, category_balance, load_dataset, load_external, load_scenarios_jsonl,
)
from experiments.signal_gov.delong import delong_roc_test
from experiments.signal_gov.features import (
    FeatureVector, build_extractor, write_features_jsonl,
)
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

logger = logging.getLogger(__name__)

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
        "inv_text_confidence_top1": [1.0 - f.text_confidence_top1 for f in features],
        "entropy": [f.entropy for f in features],
        "inv_coherence": [1.0 - f.coherence for f in features],
        "vritti_risk": [f.vritti_risk for f in features],
        "jepa_disagreement": [f.jepa_disagreement for f in features],
    }


def run(mode: str, dataset: str, out_dir: Path, *, seed: int = 1234,
        features_path: str | None = None, n_boot: int = 2000,
        make_plots: bool = True, checkpoint: str | None = None,
        real_cg_stub: bool = False, strict_signals: bool = False,
        tier: str = "consumer", external_path: str | None = None,
        hf_model: str | None = None, hf_mock: bool = False,
        scenarios_path: str | None = None,
        cg_quantize: str | None = None, cg_device: str = "auto",
        write_cache: bool = True, cg_state_dict: str | None = None,
        allow_untrained_cg_head: bool = False) -> ExperimentResult:
    if scenarios_path:
        scenarios = load_scenarios_jsonl(scenarios_path)
    elif dataset in ("agentdojo", "injecagent") and external_path:
        scenarios = load_external(dataset, external_path)
    else:
        scenarios = load_dataset(dataset)

    # Label integrity: authored labels must match the rule-based oracle.
    mismatches = verify_consistency(scenarios)
    if mismatches:
        ids = ", ".join(sid for sid, _ in mismatches)
        raise RuntimeError(f"oracle/authored label mismatch for: {ids}")

    labels = _labels_from_oracle(scenarios)

    # CG adapter wiring for live (non-stub) real_cg.
    extra: dict = {}
    if mode == "real_cg" and not real_cg_stub:
        if cg_state_dict:
            # Load the TRAINED CG head into a wrapper -> adapter. Fail-closed inside
            # load_cg_adapter if the checkpoint is vanilla/untrained (unless allowed).
            from experiments.signal_gov.cg_checkpoint import load_cg_adapter
            extra = {"adapter": load_cg_adapter(
                base_model=checkpoint, state_dict_path=cg_state_dict,
                quantize=cg_quantize, device_map=cg_device,
                allow_untrained=allow_untrained_cg_head)}
        else:
            logger.warning(
                "real_cg without --cg-state-dict: CG head is UNTRAINED (base backbone "
                "'%s' only) -> degenerate 32-D state, PLUMBING ONLY. Pass --cg-state-dict "
                "<trained *_model.pt> for a real-signal run.", checkpoint)
            extra = {"quantize": cg_quantize, "device_map": cg_device}
    extractor = build_extractor(mode, seed=seed, features_path=features_path,
                                checkpoint=checkpoint, use_stub=real_cg_stub,
                                strict_signals=strict_signals, tier=tier,
                                hf_model=hf_model, use_mock_hf=hf_mock, **extra)
    features = extractor.extract_all(scenarios)

    # Persist a reusable feature cache for the extraction modes (real_cg,
    # real_checkpoint_cached) so the expensive forward passes are done once and C1-C4
    # can be re-evaluated offline with `--mode cached --features <out>/features.jsonl`.
    # The cache schema is identical to the `cached` reader (all FEATURE_FIELDS, incl.
    # provenance). Enabled by default; disable with --no-cache-write.
    cache_path = None
    if write_cache and mode in ("real_cg", "real_checkpoint_cached"):
        out_dir.mkdir(parents=True, exist_ok=True)
        cache_path = out_dir / "features.jsonl"
        write_features_jsonl(features, cache_path)

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

    # Variant baselines (e.g. C3b top-1 confidence): scored + reported alongside,
    # but kept OUT of the nested ordering check so the C1..C4 story stays clean.
    from experiments.signal_gov.metrics import catch_at_budget as _catch_var
    variant_scores = score_variant_configs(scenarios, features)
    variant_metrics: Dict[str, Dict] = {}
    for name in VARIANT_CONFIG_ORDER:
        scores = variant_scores[name]
        m = per_config_metrics(labels, scores, BUDGETS_DEFAULT)
        m["catch_at_budget"] = {
            f"{b:.2f}": _catch_var(labels, scores, b, tiebreak) for b in BUDGETS_DEFAULT
        }
        _, lo, hi = bootstrap_ci(labels, scores, roc_auc, n_boot=n_boot, seed=seed)
        m["auroc_ci95"] = [lo, hi]
        variant_metrics[name] = m

    # Ablation ordering on AUROC (NaN-safe).
    ordered_aucs = [aurocs[n] for n in CONFIG_ORDER]
    ordering_ok = all(
        (b >= a - 1e-9)
        for a, b in zip(ordered_aucs, ordered_aucs[1:])
        if not (np.isnan(a) or np.isnan(b))
    )

    # DeLong: C4 vs C3 (verbalized-confidence baseline — the primary comparison).
    c3, c4 = CONFIG_ORDER[2], CONFIG_ORDER[3]
    auc_c3, auc_c4, p_val = delong_roc_test(labels, scores_by_config[c3], scores_by_config[c4])
    delong_block = {
        "config_a": c4, "config_b": c3,
        "auc_c4": auc_c4, "auc_c3": auc_c3,
        "delta_auroc": auc_c4 - auc_c3, "p_value": p_val,
    }

    # DeLong: C4 vs C3b (top-1-confidence baseline — baseline-sensitivity check).
    delong_c3b_block = None
    if VARIANT_CONFIG_ORDER:
        c3b = VARIANT_CONFIG_ORDER[0]
        auc_c3b, auc_c4b, p_c3b = delong_roc_test(
            labels, variant_scores[c3b], scores_by_config[c4])
        delong_c3b_block = {
            "config_a": c4, "config_b": c3b,
            "auc_c4": auc_c4b, "auc_c3b": auc_c3b,
            "delta_auroc": auc_c4b - auc_c3b, "p_value": p_c3b,
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
            "feature_cache": str(cache_path) if cache_path else None,
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
        "variant_configs": variant_metrics,
        "delong_c4_vs_c3": delong_block,
        "delong_c4_vs_c3b": delong_c3b_block,
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
    mode = meta["mode"]
    disclaimer = None
    if mode == "mock":
        disclaimer = ("> ⚠️ **Not a result.** This run uses `mock` SYNTHETIC features and "
                      "validates the harness only. Scientific conclusions require real "
                      "features, the full balanced benchmark, and a held-out split.")
    elif mode == "real_cg" and "stub" in prov:
        disclaimer = ("> ⚠️ **Plumbing validation, not evidence.** This `real_cg` run uses a "
                      "deterministic STUB 32-D state (`StubCGLLMAdapter`), not live inference. "
                      "The extraction path (sovereign_bridge → entropy/vritti adapters → JEPA) "
                      "executes end-to-end, but the state is a FIXED fixture, so internal "
                      "signals are constant across scenarios and carry NO discriminative claim "
                      "(AUROC(C4)==AUROC(C3) is expected). Evidence requires a real CG "
                      "checkpoint + the full balanced benchmark + a held-out split.")
    elif mode == "real_checkpoint_cached" or "real_checkpoint_cached" in prov or "PROXY" in prov:
        is_mock = "mock-hf" in prov
        disclaimer = ("> ⚠️ **" + ("Plumbing validation (mock backend), not evidence."
                      if is_mock else "Pilot, not a full result.") + "** "
                      "`real_checkpoint_cached`: `entropy` is REAL predictive entropy from the "
                      "model logits, but `coherence`/`vritti`/`jepa` come from a hidden-state → "
                      "32-D **PROXY** projection (unvalidated placeholder, NOT the CG path). "
                      + ("The mock backend is deterministic and label-blind. " if is_mock else
                         "Intended as a 30-50 scenario pilot before any 400-600 full run. ")
                      + "No benchmark success claim.")
    elif mode == "cached" and "stub" in prov:
        disclaimer = ("> ⚠️ **Plumbing validation, not evidence.** Cached features were "
                      "produced from a deterministic STUB CG state (no discriminative claim).")
    if disclaimer:
        lines.append(disclaimer)
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

    # Baseline-sensitivity: C3 (verbalized) vs C3b (top-1) confidence vs C4.
    vc = results.get("variant_configs") or {}
    db = results.get("delong_c4_vs_c3b")
    if vc:
        c3m = results["configs"][CONFIG_ORDER[2]]
        c4m = results["configs"][CONFIG_ORDER[3]]
        lines.append("## Baseline sensitivity: verbalized (C3) vs top-1 (C3b) confidence")
        lines.append("")
        lines.append("C3 uses a VERBALIZED safety score elicited from the model; C3b is the same "
                     "config with TOP-1 next-token confidence instead (a parallel baseline, NOT "
                     "part of the nested C1..C4 ordering). This shows whether C4's edge survives a "
                     "different — possibly stronger — confidence baseline.")
        lines.append("")
        lines.append("| Config | Confidence source | AUROC | AUROC 95% CI | AUPRC | catch@10% |")
        lines.append("|---|---|---|---|---|---|")

        def _row(label, src, m):
            ci = m.get("auroc_ci95", [float("nan"), float("nan")])
            return (f"| {label} | {src} | {m['auroc']:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] | "
                    f"{m['auprc']:.3f} | {m['catch_at_budget']['0.10']:.3f} |")

        lines.append(_row("C3", "verbalized", c3m))
        for name in VARIANT_CONFIG_ORDER:
            lines.append(_row(name, "top-1 token", vc[name]))
        lines.append(_row("C4", "+ internal signals", c4m))
        lines.append("")
        if db:
            pvb = db["p_value"]
            lines.append(f"- **C4 vs C3b (DeLong):** AUROC(C4) = {db['auc_c4']:.3f}, "
                         f"AUROC(C3b) = {db['auc_c3b']:.3f}, Δ = {db['delta_auroc']:+.3f}, "
                         f"p = {'nan (too few per class)' if np.isnan(pvb) else f'{pvb:.4f}'}")
            lines.append("")

    # Power / significance disclaimer (auto, for small-N pilots).
    n = ds["n_total"]
    npos = ds["n_positive"]
    nneg = n - npos
    underpowered = n < 100 or min(npos, nneg) < 20
    power_notes = []
    if underpowered:
        power_notes.append(
            f"**N={n} (pos={npos}, neg={nneg}) is small.** Bootstrap CIs are wide and the "
            "DeLong test is UNDERPOWERED — a non-significant or borderline p-value at this N "
            "is NOT evidence of no effect, and a significant one needs replication. Treat a "
            "30-50 scenario run as a directional pilot, not a confirmatory result.")
    if np.isnan(pv):
        power_notes.append("DeLong p-value is undefined (need ≥2 samples per class).")
    elif pv > 0.05:
        power_notes.append(f"C4 vs C3 is NOT significant at p<0.05 (p={pv:.3f}).")
    if power_notes:
        lines.append("## Power & significance")
        lines.append("")
        for nt in power_notes:
            lines.append(f"- {nt}")
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
    lines.append("See `Project_documentation/governance/experiments/signal_gov/README.md` for the pre-registered "
                 "success/failure criteria the *real* experiment is judged against.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Signal-governance experiment harness")
    p.add_argument("--mode",
                   choices=["mock", "cached", "real_cg", "real_checkpoint_cached"],
                   default="mock")
    p.add_argument("--dataset", default="smoke",
                   help="handbuilt | smoke | agentdojo_fixture | injecagent_fixture | "
                        "external_fixtures | agentdojo | injecagent")
    p.add_argument("--external-path", default=None,
                   help="path to an exported AgentDojo/InjecAgent JSON (with "
                        "--dataset agentdojo|injecagent)")
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--features", default=None, help="path to cached features (.jsonl/.parquet)")
    p.add_argument("--checkpoint", default=None, help="CG checkpoint for real_cg mode")
    p.add_argument("--real-cg-stub", action="store_true",
                   help="real_cg via StubCGLLMAdapter (torch-free plumbing validation)")
    p.add_argument("--strict-signals", action="store_true",
                   help="real_cg: raise instead of fail-closed when a signal is missing")
    p.add_argument("--tier", default="consumer", help="governance tier for real_cg")
    p.add_argument("--hf-model", default=None,
                   help="stock HF model for --mode real_checkpoint_cached (Qwen/Llama/Mistral)")
    p.add_argument("--hf-mock", action="store_true",
                   help="real_checkpoint_cached via a deterministic mock backend (no torch)")
    p.add_argument("--scenarios", default=None,
                   help="load Scenario records directly from a JSONL (e.g. the assembled pilot)")
    p.add_argument("--cg-quantize", default=None, choices=[None, "4bit", "8bit"],
                   help="MistralCGAdapter quantization for --mode real_cg (needs bitsandbytes)")
    p.add_argument("--cg-device", default="auto",
                   help="MistralCGAdapter device_map for --mode real_cg")
    p.add_argument("--cg-state-dict", default=None,
                   help="trained CG wrapper state-dict for --mode real_cg "
                        "(e.g. checkpoints_unified/best_model.pt); --checkpoint stays the "
                        "BASE backbone id. Fails closed if the checkpoint looks "
                        "vanilla/untrained.")
    p.add_argument("--allow-untrained-cg-head", action="store_true",
                   help="proceed even if --cg-state-dict looks vanilla/untrained (plumbing only)")
    p.add_argument("--no-cache-write", action="store_true",
                   help="do not write features.jsonl (real_cg / real_checkpoint_cached "
                        "write a reusable cache by default)")
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
              tier=args.tier, external_path=args.external_path,
              hf_model=args.hf_model, hf_mock=args.hf_mock,
              scenarios_path=args.scenarios, cg_quantize=args.cg_quantize,
              cg_device=args.cg_device, write_cache=not args.no_cache_write,
              cg_state_dict=args.cg_state_dict,
              allow_untrained_cg_head=args.allow_untrained_cg_head)
    r = res.results
    print(f"[signal_gov] mode={args.mode} dataset={args.dataset} "
          f"N={r['dataset']['n_total']} unsafe={r['dataset']['n_positive']}")
    for name in CONFIG_ORDER:
        m = r["configs"][name]
        print(f"  {name:32s} AUROC={m['auroc']:.3f}  catch@10%={m['catch_at_budget']['0.10']:.3f}")
    for name in VARIANT_CONFIG_ORDER:
        m = r.get("variant_configs", {}).get(name)
        if m:
            print(f"  {name:32s} AUROC={m['auroc']:.3f}  "
                  f"catch@10%={m['catch_at_budget']['0.10']:.3f}  (variant baseline)")
    print(f"  ordering C4>=C3>=C2>=C1: {'PASS' if r['ordering_ok'] else 'FAIL'}")
    db = r.get("delong_c4_vs_c3b")
    if db:
        pvb = db["p_value"]
        print(f"  C4 vs C3b (top-1 baseline): dAUROC={db['delta_auroc']:+.3f}  "
              f"p={'nan' if np.isnan(pvb) else f'{pvb:.4f}'}")
    print(f"  artifacts -> {res.out_dir}")
    if r["meta"].get("feature_cache"):
        print(f"  feature cache -> {r['meta']['feature_cache']}  "
              "(offline replay: --mode cached --features <path>)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
