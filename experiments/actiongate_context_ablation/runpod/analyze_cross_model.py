"""Aggregate all available per-model results into the cross-model report + plots.

Discovers every durable run under RESULTS_ROOT that has a results.json, plus the
committed Qwen-7B result, and writes CROSS_MODEL_RESULTS.md (repo), the JSON, and
the plots. Honest: models that did not run are simply absent (listed as pending).
"""

from __future__ import annotations

import json
import os
import pathlib

import runpod_common as RC
import cross_model as CM


def _discover_dirs():
    dirs = []
    # committed Qwen-7B result (frozen evidence)
    committed = RC.EXPERIMENT_DIR / "results" / "qwen7b_primary_real_llm"
    if committed.exists():
        dirs.append(str(committed))
    # per-model runs under RESULTS_ROOT
    root = pathlib.Path(os.environ.get("RESULTS_ROOT", "/workspace/results/actiongate-context-qwen"))
    if root.exists():
        for d in sorted(root.iterdir()):
            if d.is_dir() and (d / "results.json").exists():
                dirs.append(str(d))
    return dirs


def main():
    dirs = _discover_dirs()
    models = CM.discover(dirs)
    out_md = RC.EXPERIMENT_DIR / "CROSS_MODEL_RESULTS.md"
    out_md.write_text(CM.render_investor_md(models) + "\n")

    out_root = pathlib.Path(os.environ.get(
        "RESULTS_ROOT", "/workspace/results/actiongate-context-qwen")) / "cross_model"
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "cross_model_results.json").write_text(
        json.dumps(CM.to_json(models), indent=2, sort_keys=True) + "\n")
    try:
        import cross_model_plots as P
        plots = P.render(models, out_root / "plots")
    except Exception as e:   # matplotlib optional
        plots = []
        (out_root / "plots_SKIPPED.txt").write_text(f"plots skipped: {e!r}\n")

    v = CM.verdict(models)
    print(json.dumps({"n_models": len(models),
                      "n_real": sum(1 for m in models if m.is_real),
                      "verdict": v["verdict"], "report": str(out_md),
                      "plots": plots}, indent=2))


if __name__ == "__main__":
    main()
