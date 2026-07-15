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
gates.py                 PRE-REGISTERED thresholds → one verdict label
capture_kv.py            POD: capture real post-RoPE Q/K/V + frozen mask (no fork needed)
fakequant_quality.py     POD: end-to-end fake-quant ppl + token-agreement (no fork needed)
SPEC.md                  current-format + candidate-format specification (code-cited)
RESULT_SCHEMA.md         JSON/CSV result schemas
STATUS.md                what is CPU-tested vs pod-required, and what result justifies kernel work
tests/                   CPU unit tests (quantizer↔production fidelity, accounting, gates)
run_*.sh / run_all.sh    orchestration (CPU offline evals + pod capture/e2e)
```

## Run
```bash
cd experiments/kvpro_v3_symmetric_residual

# CPU-runnable now (plumbing + analytical): unit tests, accounting, synthetic pipeline
python3 -m unittest tests.test_symmetric_residual_cpu -v
python3 accounting.py
bash run_all.sh --reconstruction-only        # synthetic fixture if no real capture (NOT a verdict)

# On a GPU pod (the real falsifier):
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt   # or build via calibrate
bash run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask "$PROTECT_MASK_PATH"
#   -> capture real KV -> reconstruction + attention-error -> fake-quant e2e -> verdict.json + CSV
bash run_all.sh --quality-only               # attn + e2e + gate (reuses an existing capture)
```

## Honesty rules (enforced in code)
- Every result is labeled **MEASURED** / **NOT RUN** / **NOT_A_VERDICT_SYNTHETIC**.
- Reconstruction MSE is **never** the sole decision metric — the attention-output error + end-to-end are.
- Thresholds are **pre-registered** in `gates.py` and not loosened after seeing results.
- Analytical bandwidth numbers are **not** presented as measured TPS.
- If symmetric fails on Qwen2.5-7B, the verdict says so plainly (`NO_GO_QUALITY`).
- Scope is strictly xmin-removal-via-symmetric; **no** sparse attention / rotation / TP / WarmTier.

See `STATUS.md` for exactly what is decided vs still pod-required, and `SPEC.md` for the formats.
