# RUNPOD_QWEN_TROUBLESHOOTING

| symptom | cause | fix |
|---|---|---|
| `CUDA unavailable — refusing CPU fallback` | no GPU / wrong torch build | use a CUDA template; reinstall torch with the cu121 index (`bash setup_runpod.sh`). A primary run must never run on CPU. |
| `VRAM x GB < required 24 GB` | GPU too small for 7B | use a ≥24 GB GPU, or set `MIN_VRAM_GB` lower only for the 0.5B smoke. |
| `model incomplete at ...` | interrupted/partial download | re-run `python3 download_model.py` (resumes); or `FORCE_DOWNLOAD=1 python3 download_model.py`. |
| `repository tree is dirty` | uncommitted changes on the pod | commit/stash, or `ALLOW_DIRTY=1` (records the dirty state; not for a citable run). |
| `benchmark cannot import` | deps missing / wrong cwd | run from `.../runpod`; `bash setup_runpod.sh`; check `pip show transformers`. |
| `primary/smoke run requires a real model; refusing mock` | `ALLOW_MOCK=1` on a real run | unset `ALLOW_MOCK`; ensure the model downloaded and torch sees the GPU. |
| `resume guard: 'model_revision' changed` | different model snapshot than the run started with | use the original revision, or start a new `RUN_ID`. Never mix revisions in one run. |
| `resume guard: 'frozen_fingerprint' changed` | frozen code changed since the run began | check out the original commit; the benchmark surface must be identical to resume. |
| `duplicate result key with differing prompt` | corrupted/edited `records.jsonl` | inspect the run dir; start a fresh `RUN_ID`. Do not hand-edit records. |
| `smoke/primary records mixed` | reused a smoke `RUN_ID` for primary | use distinct `RUN_ID`s (`smoke_*` vs `primary_*`). |
| CUDA OOM during generation | batch/seq too large | lower `MAX_NEW_TOKENS`; ensure `DTYPE=auto` (BF16/FP16); OOM is recorded per-example as `status=ERROR:*` and the run continues — resume after freeing memory. |
| HF download 401/403 | gated repo / bad token | set `HF_TOKEN`; accept the model license on HuggingFace. |
| `huggingface.co` unreachable | network policy blocks HF | use a pod/network with HF egress; the token is read only from `HF_TOKEN`. |
| chat template warnings | tokenizer lacks a chat template | Qwen2.5-Instruct ships one; verify `MODEL_ID` is the *Instruct* variant. |
| Gemma-2 run: **every record `status=ERROR`**, `is_real: false`, run skipped | Gemma-2 needs the *eager* attention impl (soft-capping + sliding window); the default SDPA/FlashAttention kernels raise on every generation | Handled automatically: `run_benchmark.build_client` injects `attn_implementation='eager'` for any `gemma-2` model. Ensure you're on the current runpod code (`git pull`). The `error` field on each record now carries the underlying message for diagnosis. The frozen client bytes and fingerprint are unchanged (fix lives in the non-frozen runner). |
| Re-running after a code fix shows `new_records: 0` and the SAME failure | durable **resume** treats every already-written record (including `status=ERROR:*`) as done and skips it, so a fix never executes on a run that previously errored end-to-end | delete the stale run dir (or use a fresh `RUN_ID`) so the run re-executes from scratch: `rm -rf $RESULTS_ROOT/<RUN_ID>` then re-run. Resume is for *interrupted* runs, not for retrying errors after changing code. |
| plots missing | matplotlib not installed | `pip install matplotlib==3.9.2`; reports still generate without plots. |

## Verifying a run is scientific
`verify_results.py` must report `ok: true`, `n_missing: 0`, `is_real: true`, and
`run_kind: PRIMARY`. If `is_real` is false, the records came from the mock reader
and the run is **non-scientific** (`BLOCKED_NO_MODEL`).

## Where to look
- `run_config.json` — the frozen config + revision + fingerprint the run committed to.
- `environment_probe.json` — GPU/driver/versions at run time.
- `verify_report.json` — completeness/integrity result.
- `records.jsonl` — one durable line per (method, budget, context, task).
