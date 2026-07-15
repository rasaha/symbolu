# KVPro V3 Gate-1 — Symmetric INT4 on Protected-Residual Channels (falsification study)

**Isolated experiment. Modifies no production code, no production format, and builds no CUDA kernel.**
It answers one question, four ways, before anyone spends kernel effort:

> After KVPro separates the protected/outlier channels, do the remaining **inlier** channels tolerate
> **symmetric signed INT4** (dropping per-block/per-token **xmin** + the affine add) — and does that
> removal actually remove enough decode work to justify a kernel?

This is a **falsification** study — it is built to find the truth, not to confirm the hypothesis.
Its four questions (all pre-registered):
1. Does symmetric residual quant **preserve quality**? (reconstruction + attention-output error + end-to-end)
2. How much metadata/instruction work does it **actually remove**? (`accounting.py`, analytical)
3. Does that removed work sit **on the critical GPU path**? (bandwidth-bound proxy; and does protect dominate after?)
4. What is the resulting **verdict**? (`gates.py`, one of 5 labels)

## Why this is a fake-quant study (and does NOT need the int4 fork)
Quality is measured by **quantize→dequantize in fp** (fake-quant) and by an offline attention-error
proxy on **real captured K/V**. Neither needs the int4 CUDA kernel or the `int4_protected` backend.
So the harness reports the int4 fork as **INFO, not a gate** — this is stated openly (not a silent
fallback). A future V3 *kernel prototype* would need the fork; this Gate-1 does not. Real hard deps for
the pod steps: **GPU + model weights + the calibrated protect mask.**

## Layout
```
quantizers.py            affine (== production) + symmetric S1–S4, residual-only, protected exact
metrics.py               MSE/cos/maxabs, per-head, protected-vs-unprotected, QKᵀ/softmax/attn-output error
accounting.py            analytical bytes/token, metadata, ops removed (Qwen2.5-7B, Llama-3.1-8B)
reconstruction_eval.py   low-level error (real capture or --synthetic plumbing fixture)
attention_error_eval.py  DECISIVE offline proxy (logits→softmax→output), relative to affine
gates.py                 PRE-REGISTERED gate → one verdict (needle+hard-needle+MMLU REQUIRED for GO)
results.py               pure parsing/aggregation/regression detection (CPU-tested)
capture_kv.py            POD: capture real post-RoPE Q/K/V + frozen mask (no fork needed)
fakequant_model.py       POD: shared fake-quant generation backend (per-candidate KV cache)
needle_driver.py         POD: STANDARD needle — reuses verify_phase5b_5_needle protocol
hard_needle_driver.py    POD: HARD-needle (MANDATORY) — reuses phase6k12_hard_needle build_item/classify
mmlu_driver.py           POD: MMLU/knowledge — reuses bench_phase6n build_prompt/parse_answer/_load_mmlu
token_agreement.py       POD: teacher-forced AND autoregressive agreement (separate, secondary)
fakequant_quality.py     POD: perplexity + token-agreement (secondary signal)
SPEC.md / RESULT_SCHEMA.md / STATUS.md   format spec / result schemas / status + RunPod sequence
tests/                   CPU unit tests (quantizer↔production, accounting, results, gate, builder reuse)
run_*.sh / run_all.sh    orchestration (CPU offline evals + pod quality drivers)
```

The end-to-end drivers **reuse the repo's existing quality battery** (same prompts, scoring,
seeds, acceptance conventions) and run it through **fake-quant** so the symmetric candidates can be
evaluated with identical scoring — no new incompatible protocol, no int4 CUDA kernel.

## Run
```bash
cd experiments/kvpro_v3_symmetric_residual

# CPU-runnable now (plumbing + analytical): unit tests, accounting
python3 -m unittest discover -s tests -p 'test_*.py'
python3 accounting.py
bash run_all.sh --reconstruction-only        # synthetic fixture if no real capture (NOT a verdict)

# On a GPU pod (the real falsifier) — Qwen2.5-7B (marginal model) FIRST:
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
bash run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --quick-quality   # fast sanity
bash run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH" --full-quality     # decisive
#   -> runs/<ts>/: needle_results.json hard_needle_results.json knowledge_results.json
#      token_agreement.json candidate_summary.csv verdict.json + logs
# Stages: --needle-only  --hard-needle-only  --mmlu-only  --quality-only
```
(See `STATUS.md` for the exact RunPod sequence and the honest hardware-untested list.)

## Honesty rules (enforced in code)
- Every result is labeled **MEASURED** / **NOT RUN** / **NOT_A_VERDICT_SYNTHETIC**.
- **GO requires standard-needle + hard-needle + MMLU** on the model under test — reconstruction /
  attention-error / perplexity / token-agreement can **never** GO alone.
- Thresholds are **pre-registered** in `gates.py` and not loosened after results.
- Analytical bandwidth numbers (~9.3% both-xmin / ~4.65% one) are **not** presented as measured TPS,
  and symmetric alone is **not** a standalone V3 throughput solution (see STATUS.md §systems).
- If symmetric fails on Qwen2.5-7B, the verdict says so plainly (`NO_GO_QUALITY`).
- Existing benchmarks are reused, never silently replaced with an easier one.
- Scope is strictly xmin-removal-via-symmetric; **no** sparse attention / rotation / TP / WarmTier.

See `STATUS.md` for exactly what is decided vs still pod-required, and `SPEC.md` for the formats.
