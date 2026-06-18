"""
run.py — drive Diagnostic D1 (signal-survival ladder) end to end.

Builds the one-forward-pass cache (real CG wrapper on GPU, or a torch-free mock for
plumbing), then runs the read-only ladder analysis and writes the localization verdict.

Usage (GPU, trained CG head):
    python -m experiments.signal_gov.diagnostics.run \
        --checkpoint mistralai/Mistral-7B-v0.3 \
        --cg-state-dict /workspace/checkpoints_unified/final_model.pt \
        --out runs/d1

Plumbing (no torch/GPU):
    python -m experiments.signal_gov.diagnostics.run --mock --out runs/d1_mock

Replay a cached forward pass offline (metric-identical, no model):
    python -m experiments.signal_gov.diagnostics.run --from-cache runs/d1/d1_cache.npz \
        --out runs/d1_replay

Output: runs/<out>/d1_report.md (the localization verdict), d1_result.json,
per_scenario.csv, and d1_cache.npz (reusable for D2-D6). No success claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from experiments.signal_gov.diagnostics.cache import (
    D1Cache, build_cache_mock, build_cache_real,
)
from experiments.signal_gov.diagnostics.ladder import (
    READOUT_KEYS, RUNG_ORDER, compute_ladder, render_report,
)
from experiments.signal_gov.falsification.scenarios import load_fabrication


def _build_cache(args) -> D1Cache:
    if args.from_cache:
        return D1Cache.load(args.from_cache)
    scenarios = load_fabrication()
    if args.limit:
        scenarios = scenarios[: args.limit]
    if args.mock:
        return build_cache_mock(scenarios, tier=args.tier, seed=args.seed)
    from experiments.signal_gov.cg_checkpoint import load_cg_adapter
    adapter = load_cg_adapter(
        base_model=args.checkpoint, state_dict_path=args.cg_state_dict,
        quantize=args.cg_quantize, device_map=args.cg_device,
        allow_untrained=args.allow_untrained_cg_head)
    return build_cache_real(scenarios, adapter, tier=args.tier, strict=args.strict_signals,
                            cache_all_layers=not args.no_all_layers)


def run(args) -> int:
    cache = _build_cache(args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.from_cache and not args.no_cache_write:
        cache.save(out_dir / "d1_cache.npz")

    result = compute_ladder(cache, tau=args.tau, n_boot=args.n_boot, seed=args.seed)
    prov = cache.provenance[0] if cache.provenance else ""

    (out_dir / "d1_report.md").write_text(render_report(result, provenance=prov),
                                           encoding="utf-8")
    _write_per_scenario(out_dir / "per_scenario.csv", cache)
    (out_dir / "d1_result.json").write_text(json.dumps(_result_json(result), indent=2),
                                            encoding="utf-8")

    print(f"[d1] N={result.n} unsafe={result.n_unsafe} fool_rate={_f(result.fool_rate)} "
          f"confident(unsafe={result.confident_unsafe}, safe={result.confident_safe})")
    print("[d1] ladder AUROC on the fooled subset:")
    for key in RUNG_ORDER:
        print(f"     {key:14s} full={_f(result.aurocs_full.get(key))} "
              f"subset={_f(result.aurocs_subset.get(key))}")
    for key in READOUT_KEYS:
        print(f"     {key:18s} subset={_f(result.aurocs_subset.get(key))}")
    print("[d1] drops:", {k: _f(v) for k, v in result.drops.items()})
    print(f"\n  ===> VERDICT: {result.headline}  ({result.verdict})")
    print(f"  selects: {result.r_select}")
    print(f"\n  report -> {out_dir / 'd1_report.md'}")
    return 0


def _f(x):
    return "nan" if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x:.3f}"


def _write_per_scenario(path: Path, cache: D1Cache) -> None:
    rows = cache.scalar_table()
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _result_json(r) -> dict:
    return {
        "n": r.n, "n_unsafe": r.n_unsafe, "tau": r.tau, "fool_rate": r.fool_rate,
        "confident_n": r.confident_n, "confident_unsafe": r.confident_unsafe,
        "confident_safe": r.confident_safe, "alphas": r.alphas,
        "aurocs_full": r.aurocs_full, "aurocs_subset": r.aurocs_subset,
        "aurocs_subset_ci": r.aurocs_subset_ci, "probe_per_alpha": r.probe_per_alpha,
        "drops": r.drops, "verdict": r.verdict, "headline": r.headline,
        "r_select": r.r_select, "detail": r.detail, "thresholds": r.thresholds,
    }


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Diagnostic D1 — signal-survival ladder")
    p.add_argument("--checkpoint", default="mistralai/Mistral-7B-v0.3",
                   help="base backbone (HF id or local dir)")
    p.add_argument("--cg-state-dict", default=None,
                   help="trained CG wrapper state-dict (e.g. checkpoints_unified/final_model.pt)")
    p.add_argument("--cg-quantize", default=None, choices=[None, "4bit", "8bit"])
    p.add_argument("--cg-device", default="auto")
    p.add_argument("--allow-untrained-cg-head", action="store_true")
    p.add_argument("--strict-signals", action="store_true")
    p.add_argument("--mock", action="store_true",
                   help="torch-free deterministic cache (CI plumbing; no result claim)")
    p.add_argument("--from-cache", default=None,
                   help="replay a saved d1_cache.npz instead of running a forward pass")
    p.add_argument("--no-all-layers", action="store_true",
                   help="cache only the final-layer hidden (smaller cache; D1 still works)")
    p.add_argument("--no-cache-write", action="store_true")
    p.add_argument("--out", default="runs/d1")
    p.add_argument("--tau", type=float, default=0.5, help="confidence threshold for 'fooled'")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--tier", default="consumer")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if not args.mock and not args.from_cache and not args.cg_state_dict:
        print("ERROR: pass --cg-state-dict <trained *_model.pt> for a live run, "
              "--mock for a torch-free plumbing run, or --from-cache <npz> to replay.",
              file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
