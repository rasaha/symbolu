"""Build V2 absolute-utility reports from durable records (V2 verdict/scoring).

Mirror of collect.py for the V2 benchmark: reuses run_benchmark.build_result_v2 and
real_llm_bench_v2's to_json / render_report_md. Refuses to run over V1 records.
"""

from __future__ import annotations

import csv
import json
import pathlib

import runpod_common as RC
import run_benchmark as RB

from actiongate_context_ablation import real_llm_bench_v2 as R2


def _write_csv(result_json, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "budget", "token_reduction", "decision_preservation",
                    "envelope_preservation", "protected_recall", "task_accuracy",
                    "hallucination_rate", "mean_latency_ms", "cost_estimate_usd", "n_contexts"])
        for c in result_json["cells"]:
            w.writerow([c["method"], c["budget"], c["token_reduction"],
                        c["decision_preservation"], c["envelope_preservation"],
                        c["protected_recall"], c["task_accuracy"], c["hallucination_rate"],
                        c["mean_latency_ms"], c["cost_estimate_usd"], c["n_contexts"]])


def build_reports(config=None, *, out_dir=None) -> dict:
    config = config or RC.load_config()
    if config.get("benchmark_version", "v1") != "v2":
        raise RuntimeError("collect_v2 requires BENCHMARK_VERSION=v2")
    out_dir = pathlib.Path(out_dir) if out_dir else RC.run_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    recs = RC.read_records(RC.records_path(config))
    versions = {r.get("benchmark_version", "v1") for r in recs}
    if versions and versions != {"v2"}:
        raise RuntimeError(f"refusing to score mixed/non-v2 records: versions={versions}")

    result = RB.build_result_v2(recs)
    is_real = bool(recs) and all(r.get("is_real") for r in recs)
    rec, detail = result["recommendation"], result["success_criteria"]

    RC.write_json_atomic(out_dir / "results.json", result)
    _write_csv(result, out_dir / "results.csv")
    # rebuild the markdown from the same cells (build_result_v2 already applied the verdict)
    from actiongate_context_ablation import real_llm_bench_v2 as R2m
    cells = RB.records_to_cells_v2(recs)
    (out_dir / "ABSOLUTE_UTILITY_V2_RESULTS.md").write_text(
        R2m.render_report_md(rec, detail, cells, is_real) + "\n")
    return {"out_dir": str(out_dir), "recommendation": rec, "is_real": is_real,
            "n_records": len(recs)}


def main():   # pragma: no cover
    print(json.dumps(build_reports(), indent=2))


if __name__ == "__main__":
    main()
