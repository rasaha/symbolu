#!/usr/bin/env python3
"""Evaluate the Guna/Vritti probe predictions -> metrics + decision label. torch-free (numpy); reads the
predictions.json written by the trainer (or synthesizes for --dry-run). Doc:
docs/CG_TRAINING_GUNA_VRITTI_HARNESS.md. No model-as-judge; Bhava not evaluated (not a target).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
from conscious_generation_training import guna_vritti_metrics as M           # noqa: E402
from conscious_generation_training import surface_baseline as SB             # noqa: E402
from conscious_generation_training.guna_vritti_heads import (                # noqa: E402
    formula_available, GUNA_DIM, VRITTI_DIM, DECISIONS)


def evaluate(preds: dict, surface: dict | None = None) -> dict:
    g = M.guna_metrics(np.array(preds["guna_scores"]), np.array(preds["guna_labels"]))
    v = M.vritti_metrics(np.array(preds["vritti_probs"]), np.array(preds["vritti_labels"]))
    decision = M.decide(formula_ok=formula_available(), label_source=preds.get("label_source", "synthetic"),
                        guna=g, vritti=v)
    rep = {"n": preds.get("n", len(preds["vritti_labels"])),
           "label_source": preds.get("label_source", "synthetic"),
           "guna_metrics": g, "vritti_metrics": v, "decision": decision}
    if surface is not None:
        rep["surface_baseline"] = surface
        rep["surface_confounded_labels"] = surface.get("surface_confounded_labels", [])
    return rep


def to_markdown(rep: dict) -> str:
    g, v = rep["guna_metrics"], rep["vritti_metrics"]
    L = ["# Guna/Vritti probe — evaluation", "",
         f"- n: **{rep['n']}**  ·  label_source: **{rep['label_source']}**  ·  **DECISION: `{rep['decision']}`**",
         "", "## Guna (sigmoid 6-D, BCE)",
         f"- BCE: {g['bce']}  ·  macro-AUROC: {g['macro_auroc']}  ·  micro-AUROC: {g['micro_auroc']}",
         f"- per-dim AUROC: `{g['per_dim_auroc']}`", f"- prevalence: `{g['label_prevalence']}`",
         "", "## Vritti (softmax 5-class, CE)",
         f"- CE: {v['cross_entropy']}  ·  accuracy: {v['accuracy']}  ·  macro-F1: {v['macro_f1']}",
         f"- per-class F1: `{v['per_class_f1']}`", f"- confusion: `{v['confusion']}`"]
    if "surface_baseline" in rep:
        sb = rep["surface_baseline"]
        L += ["", "## Surface-feature baseline (anti-circularity GUARDRAIL)",
              f"- threshold (confounded): **{sb['threshold']}**  ·  "
              f"surface-confounded labels: **{rep.get('surface_confounded_labels') or 'none'}**",
              f"- Guna surface AUROC: `{ {k: d.get('surface_auroc') for k, d in sb['guna'].items()} }`",
              f"- Vritti surface AUROC: `{ {k: d.get('surface_auroc') for k, d in sb['vritti'].items()} }`",
              "> A hidden-state probe must BEAT these by ≥0.05 to claim non-trivial signal. A label at"
              " surface-AUROC ≥ threshold is SURFACE_CONFOUNDED — a probe positive there is not a deep finding."]
    L += ["", "> Harness only: tests whether Guna/Vritti targets can be learned from Mistral hidden states.",
          "> NOT a Conscious-Generation training validation; no runtime change; Bhava not trained.",
          "> SYNTHETIC labels cannot validate signal -> CG_GUNA_VRITTI_SYNTHETIC_ONLY."]
    return "\n".join(L) + "\n"


def _load_rows(path):
    from pathlib import Path as _P
    return [json.loads(l) for l in _P(path).read_text().splitlines() if l.strip()]


def _synthetic_preds(n=40, seed=0):
    rng = np.random.default_rng(seed)
    return {"guna_scores": rng.random((n, GUNA_DIM)).tolist(),
            "guna_labels": (rng.random((n, GUNA_DIM)) > 0.5).astype(int).tolist(),
            "vritti_probs": rng.dirichlet(np.ones(VRITTI_DIM), n).tolist(),
            "vritti_labels": rng.integers(0, VRITTI_DIM, n).tolist(),
            "label_source": "synthetic", "n": n}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Evaluate Guna/Vritti probe predictions.")
    ap.add_argument("--checkpoint", default="runs/cg_training/guna_vritti_probe")
    ap.add_argument("--predictions", default=None, help="predictions.json (default: <checkpoint>/predictions.json)")
    ap.add_argument("--out", default="runs/cg_training/guna_vritti_probe/eval.json")
    ap.add_argument("--report", default="runs/cg_training/guna_vritti_probe/eval.md")
    ap.add_argument("--data", default=None,
                    help="labelled JSONL (prompt/response/labels) for the surface-feature baseline guardrail")
    ap.add_argument("--baseline-only", action="store_true",
                    help="compute ONLY the surface-feature baseline on --data (no probe; CPU)")
    ap.add_argument("--dry-run", action="store_true", help="synthesize predictions (plumbing only)")
    args = ap.parse_args(argv)

    if not formula_available():
        print("CG_GUNA_VRITTI_FORMULA_UNAVAILABLE"); return 1
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    # standalone guardrail: surface baseline on a labelled file, no probe needed
    if args.baseline_only:
        if not args.data:
            print("CG_GUNA_VRITTI_ENV_UNAVAILABLE: --baseline-only requires --data"); return 1
        sb = SB.surface_baseline(_load_rows(args.data))
        Path(args.out).write_text(json.dumps({"surface_baseline": sb}, indent=2))
        print(f"surface-baseline guardrail: confounded={sb['surface_confounded_labels'] or 'none'} "
              f"(threshold {sb['threshold']}); wrote {args.out}")
        return 0

    if args.dry_run:
        preds = _synthetic_preds()
    else:
        pp = Path(args.predictions or (Path(args.checkpoint) / "predictions.json"))
        if not pp.exists():
            print(f"CG_GUNA_VRITTI_ENV_UNAVAILABLE: no predictions at {pp} (run the trainer first)"); return 1
        preds = json.loads(pp.read_text())
    surface = SB.surface_baseline(_load_rows(args.data)) if args.data else None
    rep = evaluate(preds, surface=surface)
    Path(args.out).write_text(json.dumps(rep, indent=2))
    Path(args.report).write_text(to_markdown(rep))
    print(f"n={rep['n']} label_source={rep['label_source']} DECISION: {rep['decision']}"
          + (f"  surface_confounded={rep.get('surface_confounded_labels') or 'none'}" if surface else ""))
    print(f"wrote {args.out} + {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
