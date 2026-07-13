"""Build the final reports from durable records, via the FROZEN scoring/verdict.

Produces: results.json (frozen to_json), results.csv, REAL_LLM_RESULTS.md (frozen
render_report_md), and the tradeoff plots (frozen real_llm_plots). Nothing here
re-implements scoring or the verdict — it reuses real_llm_bench and run_benchmark.
"""

from __future__ import annotations

import csv
import json
import pathlib

import runpod_common as RC
import run_benchmark as RB

from actiongate_context_ablation import real_llm_bench as R


def _write_csv(result, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "budget", "token_reduction", "decision_preservation",
                    "envelope_preservation", "task_accuracy", "tool_call_correctness",
                    "hallucination_rate", "instruction_following_failure",
                    "mean_latency_ms", "cost_estimate_usd", "n_contexts"])
        for c in result.cells:
            w.writerow([c.method, c.budget, c.token_reduction, c.decision_preservation,
                        c.envelope_preservation, c.task_accuracy, c.tool_call_correctness,
                        c.hallucination_rate, c.instruction_following_failure,
                        c.mean_latency_ms, c.cost_estimate_usd, c.n_contexts])


def build_reports(config=None, *, out_dir=None, make_plots=True) -> dict:
    config = config or RC.load_config()
    out_dir = pathlib.Path(out_dir) if out_dir else RC.run_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    recs = RC.read_records(RC.records_path(config))
    result = RB.build_result(recs)

    RC.write_json_atomic(out_dir / "results.json", R.to_json(result))
    _write_csv(result, out_dir / "results.csv")
    (out_dir / "REAL_LLM_RESULTS.md").write_text(R.render_report_md(result) + "\n")

    plots = []
    if make_plots:
        try:
            from actiongate_context_ablation import real_llm_plots
            plots = real_llm_plots.render(result, out_dir / "plots")
        except Exception as e:   # matplotlib optional
            (out_dir / "plots_SKIPPED.txt").write_text(f"plots skipped: {e!r}\n")
    return {"out_dir": str(out_dir), "recommendation": result.recommendation,
            "is_real": result.is_real, "n_records": len(recs), "plots": plots}


def main():   # pragma: no cover
    print(json.dumps(build_reports(), indent=2))


if __name__ == "__main__":
    main()
