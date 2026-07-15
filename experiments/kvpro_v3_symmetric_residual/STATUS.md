# KVPro V3 Gate-1 — status (end-to-end quality harness complete)

**Date:** 2026-07-15 · **Branch:** `claude/kvpro-v2-tier1-d8b4ae` · **Current verdict: `INCONCLUSIVE`**
(the end-to-end quality drivers are built but NOT RUN — this container has no GPU).

## The gate now requires end-to-end quality (not proxies)
A candidate can receive **`GO_KERNEL_PROTOTYPE`** only if it passes **all** of, on the model under test:
**standard needle** AND **hard-needle (MANDATORY)** AND **MMLU** AND the offline attention proxy AND the
≥5% systems floor. **Reconstruction error, attention error, perplexity, and token agreement can NEVER
GO on their own** — enforced in `gates.py` (verified by `tests/test_quality_gate_cpu.py`). Qwen2.5-7B is
evaluated **first** and gets the strict rule: **zero** hard-needle regressions vs affine.

## Systems interpretation (read before acting on any GO)
- Dropping **both** K and V xmin reduces **modeled** read bytes by **~9.3%**; dropping **only one** by
  **~4.65%** (`accounting.py`, analytical).
- **This does NOT establish an equivalent TPS increase.** It is a read-bandwidth reduction; decode is
  bandwidth-bound so it is the relevant *proxy*, but the realized speedup depends on the kernel, and
  the scattered **protect** stream + the packed nibbles remain the larger costs.
- **Symmetric quantization is NOT a standalone V3 throughput solution.** ~9.3% is modest.
- **Even a passing quality result would justify kernel work only in combination with a broader
  decode-path redesign** (in-kernel paged gather + store-as-consumed layout). On its own, a passing
  Gate-1 most honestly points to `NO_GO_SYSTEMS_VALUE` unless folded into that larger kernel.

## CPU-tested this session (MEASURED-on-CPU / analytical)
- **Unit tests: 26/26 pass** — quantizer↔production fidelity + protected-exact (10);
  results parsing / per-seed aggregation / regression detection / verdict tree / NOT_RUN (11);
  driver builders **reuse** the repo needle/hard-needle/MMLU protocols (5).
- Accounting: −9.30% (both xmin) / −4.65% (one), Qwen2.5-7B & Llama-3.1-8B.
- Shell gate + `candidate_summary.csv` validated on crafted all-pass inputs (→ GO for S1/S2; S3/S4 show
  `systems=False` at 4.65%).

## NOT RUN — requires a GPU pod (the actual falsifier)
- `capture_kv.py`, `needle_driver.py`, `hard_needle_driver.py`, `mmlu_driver.py`,
  `token_agreement.py`, `fakequant_quality.py`, and `fakequant_model.py` — all need **GPU + model +
  mask** and are **HARDWARE-UNTESTED**. They do NOT need the int4 decode fork (fake-quant study).
  - Prompt-set builders (`build_prompt_set` / `build_item_set` / `build_question_set`) ARE CPU-tested
    (they reuse the repo functions); the **generation** paths are pod-only.
  - Verify against your `transformers` version: `capture_kv.py` patches `apply_rotary_pos_emb`; the
    drivers use `transformers.cache_utils.DynamicCache` + `model.generate(past_key_values=…)`.

## Exact RunPod command sequence
```bash
cd <repo-root>/experiments/kvpro_v3_symmetric_residual

# 0) mask for the marginal model first (skip if you already have one)
bash ../../scripts/kvpro_v2_validation/01_calibrate_mask.sh \
     Qwen/Qwen2.5-7B-Instruct /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt

# 1) quick gate first (small needle + hard-needle + builtin MMLU) — fast sanity
bash run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --quick-quality

# 2) full quality gate on Qwen2.5-7B (the marginal model) — the decisive run
bash run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --full-quality
#   -> runs/<ts>/ : needle_results.json hard_needle_results.json knowledge_results.json
#      token_agreement.json attention_error_metrics.json candidate_summary.csv verdict.json + logs
#   For the FULL prior MMLU battery add:  MM_ARGS real -> edit run_all (or run mmlu_driver.py --real --num-questions 200)

# 3) read the verdict
cat runs/<ts>/verdict.json ; cat runs/<ts>/candidate_summary.csv

# 4) (only if step 2 passes on Qwen) repeat on a second model
bash run_all.sh --model meta-llama/Llama-3.1-8B-Instruct --mask <llama_mask.pt> --full-quality
```
Individual stages: `--needle-only`, `--hard-needle-only`, `--mmlu-only`, `--reconstruction-only`,
`--quality-only`. Each fails loudly if GPU/model/mask are missing (no silent fallback, no easier bench).

## What result justifies kernel work
| Real pod outcome | Verdict | Action |
|---|---|---|
| S1/S2 pass needle+hard-needle+MMLU+offline **and** ≥5% (9.3% ✓) on Qwen2.5-7B | **GO_KERNEL_PROTOTYPE** | build the V3 symmetric kernel — but **only** inside the broader gather/layout redesign |
| Any candidate flips a hard-needle answer on Qwen2.5-7B (or fails a benchmark everywhere) | **NO_GO_QUALITY** | abandon symmetric residual before kernel effort |
| Quality fine but reduction <5% (single-xmin only) | **NO_GO_SYSTEMS_VALUE** | keep affine; do in-kernel gather / store-as-consumed |
| Only K (S4) or only V (S3) safe | **GO_WITH_MODIFICATION** | asymmetric format, not one universal representation |
| End-to-end not fully run | **INCONCLUSIVE** | (current state — run it on a pod) |
