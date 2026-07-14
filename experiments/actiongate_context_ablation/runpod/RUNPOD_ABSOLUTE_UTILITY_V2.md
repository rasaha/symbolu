# RunPod runbook — V2 absolute-utility benchmark

Runs the **V2** benchmark (`ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2`,
fingerprint `sha256:4b947848…`) on a real model. Reuses the existing RunPod package;
`BENCHMARK_VERSION=v2` selects the V2 tasks/scoring/prompt/fingerprint and a separate
result path. V1 and V2 records can never mix (resume guard rejects a version mismatch).

No V2 inference has been run yet — this is the exact procedure to produce it.

## Prerequisites
- A CUDA pod (≥24 GB VRAM for a 7B), the repo cloned at
  `/workspace/symbolu`, and `bash setup_runpod.sh` already run.
- `HF_TOKEN` exported for gated models. Set it without echoing:
  `read -rs HF_TOKEN; export HF_TOKEN`  (rotate any token ever pasted in plaintext).

## Primary V2 run (Qwen2.5-7B) — copy/paste
```bash
cd /workspace/symbolu/experiments/actiongate_context_ablation/runpod
git pull origin claude/token-compression-enterprise-0koy0r

export MODEL_ID="Qwen/Qwen2.5-7B-Instruct"
bash run_absolute_utility_v2.sh
RUN_ID="absolute_utility_v2_Qwen2.5-7B-Instruct" bash collect_v2.sh
cat /workspace/results/actiongate-context-qwen/absolute_utility_v2_Qwen2.5-7B-Instruct/results.json
```

## Any other model — changing MODEL_ID is the only requirement
```bash
export MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"   # or Qwen2.5-14B, Gemma-2-9b, Llama-3.1-8B
bash run_absolute_utility_v2.sh
RUN_ID="absolute_utility_v2_$(basename "$MODEL_ID")" bash collect_v2.sh
```
(Gemma-2 auto-loads with eager attention; gated models need the HF license accepted.)

## Resume an interrupted V2 run
```bash
export MODEL_ID="Qwen/Qwen2.5-7B-Instruct"
bash resume_absolute_utility_v2.sh
```
Resume is for *interrupted* runs only. To re-run after a code change, delete the run dir:
`rm -rf /workspace/results/actiongate-context-qwen/absolute_utility_v2_<model>`.

## What a valid V2 result contains
Under `/workspace/results/actiongate-context-qwen/absolute_utility_v2_<model>/`:
`records.jsonl` (each line stamped `benchmark_version: v2`), `run_config.json`
(with the V2 fingerprint + `SYSTEM_V2` hash), `verify_report.json` (`ok: true`,
`is_real: true`), `results.json` (V2 verdict + criteria), `results.csv`,
`ABSOLUTE_UTILITY_V2_RESULTS.md`, `run_manifest.json`, `SHA256SUMS`, plus the archive
one level up.

## Verdict
The frozen `real_llm_bench_v2._success` emits one of `ABSOLUTE_UTILITY_GO` /
`ABSOLUTE_UTILITY_LIMITED_GO` / `ABSOLUTE_UTILITY_STOP` / `BENCHMARK_NOT_ELIGIBLE`
(or `BLOCKED_NO_MODEL` if no real model was used). Thresholds are frozen in
`ABSOLUTE_UTILITY_V2_PREREGISTRATION.md` and were fixed before any inference.

## Preserving the result in git (ephemeral pod)
Paste the run's `results.json` + `run_manifest.json` back to the assistant, or commit
from the pod, into `results/absolute_utility_v2_<model>/` — do NOT mix with the V1
`results/qwen7b_primary_real_llm/` bundle.
```
