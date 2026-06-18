"""
run.py — drive the fabrication probe through the real CG model and emit the verdict.

Isolated: reuses the main harness's RealCGFeatureExtractor, configs (C3/C4), metrics, and
cg_checkpoint loader WITHOUT modifying them. The only "extra" computation beyond the main
harness is the raw next-token predictive entropy (the ceiling check), taken from the same
decision-point forward pass via the extractor's helper.

Usage (on a GPU pod, after training a CG head):
    python -m experiments.signal_gov.falsification.run \
        --checkpoint mistralai/Mistral-7B-v0.3 \
        --cg-state-dict /workspace/checkpoints_unified/final_model.pt \
        --out runs/falsify

Output: a SCALE or KILL/DEPRIORITIZE verdict (runs/falsify/falsification_report.md). No
success claim — see analysis.py for the pre-registered decision rule and its asymmetry.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from experiments.signal_gov.configs import CONFIG_ORDER, score_configs
from experiments.signal_gov.falsification.analysis import analyze, render_report
from experiments.signal_gov.falsification.scenarios import load_fabrication
from experiments.signal_gov.features import (
    RealCGFeatureExtractor, _decision_prompt, predictive_entropy,
)
from experiments.signal_gov.oracle import label as oracle_label


def _build_extractor(args):
    if args.real_cg_stub:
        return RealCGFeatureExtractor(use_stub=True)
    from experiments.signal_gov.cg_checkpoint import load_cg_adapter
    adapter = load_cg_adapter(
        base_model=args.checkpoint, state_dict_path=args.cg_state_dict,
        quantize=args.cg_quantize, device_map=args.cg_device,
        allow_untrained=args.allow_untrained_cg_head)
    return RealCGFeatureExtractor(adapter=adapter)


def run(args) -> int:
    scenarios = load_fabrication()
    if args.limit:
        scenarios = scenarios[: args.limit]
    labels = np.array([oracle_label(s).unsafe_label for s in scenarios], dtype=int)

    extractor = _build_extractor(args)
    feats, raw_entropy = [], []
    for s in scenarios:
        fv = extractor.extract(s)
        feats.append(fv)
        # Ceiling check: raw next-token predictive entropy at the decision point.
        try:
            raw = predictive_entropy(extractor._decision_logits(_decision_prompt(s)))
        except Exception as exc:  # stub / no real model
            print(f"  [warn] raw entropy unavailable ({type(exc).__name__}); using 0.5")
            raw = 0.5
        raw_entropy.append(raw)

    scores = score_configs(scenarios, feats)
    c3, c4 = CONFIG_ORDER[2], CONFIG_ORDER[3]
    signals = {
        "C3": scores[c3],
        "C4": scores[c4],
        "internal_risk": np.array([f.internal_risk() for f in feats], dtype=float),
        "cg_state_entropy": np.array([f.entropy for f in feats], dtype=float),
        "raw_entropy": np.array(raw_entropy, dtype=float),
    }
    verbalized_conf = np.array([f.text_confidence for f in feats], dtype=float)

    result = analyze(labels=labels, verbalized_conf=verbalized_conf, signals=signals,
                     tau=args.tau, n_boot=args.n_boot, seed=args.seed)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    prov = feats[0].provenance if feats else ""
    (out_dir / "falsification_report.md").write_text(
        render_report(result, provenance=prov), encoding="utf-8")
    _write_per_scenario(out_dir / "per_scenario.csv", scenarios, labels,
                        verbalized_conf, signals)
    (out_dir / "result.json").write_text(
        json.dumps(_result_json(result), indent=2), encoding="utf-8")

    print(f"[falsify] N={result.n} unsafe={result.n_unsafe} "
          f"fool_rate={result.fool_rate:.2f} "
          f"confident(unsafe={result.confident_unsafe}, safe={result.confident_safe})")
    for k in ("C3", "C4", "internal_risk", "cg_state_entropy", "raw_entropy"):
        print(f"  {k:18s} AUROC full={_f(result.aurocs_full.get(k))} "
              f"subset={_f(result.aurocs_subset.get(k))}")
    print(f"  C4-C3 on fooled subset: Δ={_f(result.delta_c4_c3_subset)}")
    print(f"\n  ===> VERDICT: {result.headline}  ({result.verdict})")
    print(f"  {result.detail}")
    print(f"\n  report -> {out_dir / 'falsification_report.md'}")
    return 0


def _f(x):
    return "nan" if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x:.3f}"


def _write_per_scenario(path, scenarios, labels, conf, signals):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["scenario_id", "label", "verbalized_conf", "C3", "C4",
                    "internal_risk", "cg_state_entropy", "raw_entropy"])
        for i, s in enumerate(scenarios):
            w.writerow([s.scenario_id, int(labels[i]), f"{conf[i]:.4f}",
                        f"{signals['C3'][i]:.4f}", f"{signals['C4'][i]:.4f}",
                        f"{signals['internal_risk'][i]:.4f}",
                        f"{signals['cg_state_entropy'][i]:.4f}",
                        f"{signals['raw_entropy'][i]:.4f}"])


def _result_json(r):
    return {
        "n": r.n, "n_unsafe": r.n_unsafe, "tau": r.tau, "fool_rate": r.fool_rate,
        "confident_n": r.confident_n, "confident_unsafe": r.confident_unsafe,
        "confident_safe": r.confident_safe, "aurocs_full": r.aurocs_full,
        "aurocs_subset": r.aurocs_subset, "aurocs_subset_ci": r.aurocs_subset_ci,
        "delta_c4_c3_subset": r.delta_c4_c3_subset, "verdict": r.verdict,
        "headline": r.headline, "detail": r.detail, "thresholds": r.thresholds,
    }


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Fastest-falsification of the internal-signal thesis")
    p.add_argument("--checkpoint", default="mistralai/Mistral-7B-v0.3",
                   help="base backbone (HF id or local dir)")
    p.add_argument("--cg-state-dict", default=None,
                   help="trained CG wrapper state-dict (e.g. checkpoints_unified/final_model.pt)")
    p.add_argument("--cg-quantize", default=None, choices=[None, "4bit", "8bit"])
    p.add_argument("--cg-device", default="auto")
    p.add_argument("--allow-untrained-cg-head", action="store_true")
    p.add_argument("--real-cg-stub", action="store_true",
                   help="run via StubCGLLMAdapter (pipeline smoke; raw entropy unavailable)")
    p.add_argument("--out", default="runs/falsify")
    p.add_argument("--tau", type=float, default=0.5, help="confidence threshold for 'fooled'")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--seed", type=int, default=1234)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if not args.cg_state_dict and not args.real_cg_stub:
        print("ERROR: pass --cg-state-dict <trained *_model.pt> (or --real-cg-stub for a "
              "pipeline smoke). The base backbone alone has an UNTRAINED head.", file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
