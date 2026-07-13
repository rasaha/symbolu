# RunPod Qwen execution package — ActionGate Context Minimization

Reproducible deployment/execution machinery to run the **frozen** real-LLM
validation harness on a RunPod GPU with Qwen2.5. It builds no new science: it runs
the existing benchmark (`actiongate_context_ablation.real_llm_bench`) with a real
model, durably and resumably, and produces the report + verdict via the frozen
scoring logic.

**This package changes nothing frozen** — not ActionGate, the compressor, the
extractor, the protected-span detector, the corpus, the prompts, the budgets, the
scoring thresholds, or the verdict criteria. It only adds environment probing,
model download, durable persistence + resume, verification, manifesting, and
reporting. The one runtime fix is that `TransformersLLMClient` now applies the Qwen
chat template and uses GPU BF16/FP16 (a deployment defect fix, not a prompt/scoring
change).

## Models
- Smoke (plumbing only): `Qwen/Qwen2.5-0.5B-Instruct`
- **Primary benchmark:** `Qwen/Qwen2.5-7B-Instruct`

## Files
| file | role |
|---|---|
| `setup_runpod.sh` | install pinned CUDA torch + deps, probe env |
| `probe_environment.py` | human+JSON probe; fails loudly on CUDA/VRAM/model/dirty/import problems |
| `download_model.py` | HF snapshot to `/workspace/models`, records revision, `HF_TOKEN` only |
| `run_benchmark.py` | durable, resumable runner over the frozen harness |
| `smoke_qwen.sh` | real 0.5B smoke (3–5 contexts, `original`+`protected`), rejects mock |
| `run_qwen_primary.sh` | preregistered 7B primary (full corpus, 4 methods, 20/30/40%) |
| `run_qwen_matrix.sh` | configurable matrix (overrides); defaults = primary |
| `resume_qwen_run.sh` | resume an interrupted run |
| `collect_results.sh` | verify → score/report → manifest → checksums → archive |
| `verify_results.py` | completeness + integrity + real-model check |
| `run_manifest.py` | self-describing manifest with checksums |
| `collect.py` | build results.json/csv, REAL_LLM_RESULTS.md, plots (frozen logic) |
| `requirements-runpod.txt` | pinned inference deps (torch installed separately) |
| `RUNPOD_QWEN_RUNBOOK.md` | step-by-step commands |
| `RUNPOD_QWEN_TROUBLESHOOTING.md` | failure modes and fixes |
| `RUNPOD_QWEN_RESULTS_CHECKLIST.md` | what a valid result set must contain |

## Quick start (on the pod)
```bash
cd /workspace/symbolu/experiments/actiongate_context_ablation/runpod
bash setup_runpod.sh
bash smoke_qwen.sh
bash run_qwen_primary.sh
RUN_ID=primary_qwen7b bash collect_results.sh
```

## Scientific status
Until a real Qwen run completes, the recommendation stays **`BLOCKED_NO_MODEL`**.
After a complete primary run, the FROZEN `real_llm_bench._success` emits one of
`GO` / `LIMITED_GO` / `STOP`. This package never fabricates a result: with no real
model, every path reports the blocker and refuses to emit a graded verdict.

## Outputs (under `/workspace/results/actiongate-context-qwen/<RUN_ID>/`)
`records.jsonl` (durable per-example), `run_config.json`, `environment_probe.json`,
`verify_report.json`, `results.json`, `results.csv`, `REAL_LLM_RESULTS.md`,
`plots/`, `run_manifest.json`, `SHA256SUMS`; plus `<RUN_ID>.tar.gz` (+ `.sha256`)
one level up (weights and secrets excluded).
