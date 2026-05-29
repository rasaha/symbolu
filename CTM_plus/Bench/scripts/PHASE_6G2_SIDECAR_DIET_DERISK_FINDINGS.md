# Phase 6G.2 — sidecar-diet DE-RISK analyzer (measure before you cut)

> **Status:** code + CPU regression landed and green. **The GPU capture run
> is pending on the pod** (this work was done in a CPU-only container — no
> torch/vllm/numpy). This is a **screen**, not the final quality verdict: it
> tells us, per model, whether two sidecar-*elimination* ideas are even
> plausible before we spend kernel-engineering or GPU-A/B time on them.

## Why this exists (the 6G ceiling)

Phase 6G audited the int4_protected sidecars (~3.4 GB at mml=32K, a fixed
**16.4% of KV cache**) and found the classic diet — fp8 the tensors, coarsen
the groups — tops out at **~2.5 GB** against the **~4.7 GB** HBM delta vs bf16,
because it only *shrinks* tensors. No single tensor dominates, so there's no
"delete one thing" win from shrinking alone.

The higher-leverage move is to **eliminate** metadata tensors outright by
exploiting their distribution. The metadata (scale + xmin) is **2.6 GB** —
*bigger* than the quality mechanism (k_protect_ext, 0.82 GB). Of that, the two
**xmin** tensors are 1.30 GB. If xmin is reconstructable, that's the single
biggest recoverable block. But whether it's reconstructable is **data-
dependent and per-model** — which is exactly what a cheap CPU screen should
answer before any GPU/kernel spend (the same audit→measure→implement discipline
6G/6H used).

## The two ideas this screens

The quant convention is the writer's (`phase5b_4c_paged_writer.py`):
**asymmetric**, `scale = (max − min)/15`, `xmin = min`; **K** per-channel over a
32-token block, **V** per-token over a 32-channel group.

### (B) Predicted xmin — drop `k_xmin_ext` + `v_xmin_ext` (~1.30 GB)

**Hypothesis:** per (layer, head, channel|group), the stored `xmin` is a linear
function of `scale`: `xmin ≈ α·scale + β`. This holds whenever a unit's
activation distribution is roughly self-similar across blocks (stable skew),
so `min` tracks `(max−min)`. If so, store only `scale` + a tiny per-unit
`(α, β)` (negligible: ~28×4×128×2 floats ≈ 30 KB/model) and **reconstruct xmin
in-kernel** at read time.

**Decision metric (closed form, exact):** an error δ in the reconstructed xmin
shifts *every* dequantized value in that group by δ. Relative to the quant step
(= `scale`), that error is `δ/scale` **LSBs**. So the metric is the regression
residual in LSBs: `norm_resid = resid_rms / mean_scale`, computed from the
regression sufficient statistics. It adds in quadrature with the existing
~0.5-LSB uniform-quant floor:

| `norm_resid` | extra dequant error | verdict |
|---|---|---|
| ≤ 0.25 LSB (and R² ≥ 0.98) | +~3% | **GREEN** (≈ free) |
| ≤ 0.50 LSB (and R² ≥ 0.90) | +~12% | **YELLOW** |
| > 0.50 LSB or R² < 0.90 | larger | **RED** |

### (A) Symmetric V — drop `v_xmin_ext` (~0.65 GB)

**Hypothesis:** per V group the distribution is ~centered, so a signed
*symmetric* grid (no xmin) wastes little range vs asymmetric.

**Decision metric (closed form, exact):** the symmetric-vs-asymmetric quant-step
ratio is `inflation = (absmax/7.5) / ((max−min)/15) = 2·absmax/(max−min)`. It's
**1.0** when the group is centered (`absmax ≈ range/2`, free) and **>1** when
offset (symmetric clips/coarsens, raising every V quant error by that factor).

| inflation (mean / worst) | verdict |
|---|---|
| mean ≤ 1.05, max ≤ 1.15 | **GREEN** (≈ free) |
| mean ≤ 1.30, max ≤ 1.60 | **YELLOW** |
| else | **RED** |

> Predicted-xmin **(B) subsumes (A)** for xmin — (A) is the cheaper, no-
> regression route that drops only `v_xmin`. If (B) is GREEN it dominates; (A)
> is the fallback if (B) is GREEN on K but not V (or you want to avoid the
> in-kernel α·scale+β multiply on the V path).

Both metrics are **closed form over per-group `(min, max, absmax)` + the
`(scale, xmin)` regression sufficient statistics** — accumulable online in the
capture hook, so **no raw-activation dump** is needed.

## What's validated (CPU, this container)

No GPU/torch/numpy here, so only the pure-Python decision core — but that's the
load-bearing logic.

- `test_phase6g2_diet_derisk.py` (torch-free, 10/10 PASS): linear regression
  from sufficient statistics vs hand-computed α/β/R²; the closed-form inflation
  identity; per-unit GREEN/YELLOW/RED thresholds; the dead-channel guard; the
  model rollup (one RED unit downgrades GREEN→YELLOW; 10% RED→RED); percentile
  interpolation; the recovered-GB constants tied to the 6G inventory.
- `phase6g2_sidecar_diet_derisk.py --selftest` (PASS): regression core
  (exact-fit, const-x, const-y degenerate cases), unit verdicts on tight/noisy/
  dead synthetic data, and a full `analyze_model` on a 2-layer synthetic model.

## What is NOT yet validated (needs the GPU pod)

1. **The capture run** — hook attention over the calibration corpus and
   accumulate the real per-unit statistics. Mirrors
   `calibrate_phase5b_protect_mask.py`'s hook (same corpus + leaf-attention
   heuristic) but captures **both K and V** and accumulates quant sufficient
   stats instead of max-abs.
2. **The actual per-model verdict** — whether predicted-xmin / symmetric-V are
   GREEN on Qwen-7B / Mistral-7B / Llama-3.1-8B / Qwen-14B.
3. **The downstream A/B (the real gate)** — even a GREEN screen only earns a
   real implementation + a token-agreement + hard-needle A/B vs the current
   asymmetric sidecars. The screen bounds the *quantization* error it adds; it
   does **not** prove the *model output* is preserved. That's the GPU A/B's job.

```bash
cd /workspace/symbolu
export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy
# Capture per-model stats (cheap: ~1 prefill pass over the calib corpus).
for M in Qwen/Qwen2.5-7B-Instruct mistralai/Mistral-7B-Instruct-v0.3 \
         NousResearch/Meta-Llama-3.1-8B-Instruct Qwen/Qwen2.5-14B-Instruct; do
  python CTM_plus/Bench/scripts/phase6g2_sidecar_diet_derisk.py \
    --capture --model "$M" --out "/tmp/diet_$(basename $M).json"
done
# (Re-)read any verdict on CPU later:
python CTM_plus/Bench/scripts/phase6g2_sidecar_diet_derisk.py \
  --analyze /tmp/diet_Qwen2.5-7B-Instruct.json
```

## How to read the result

- **Predicted-xmin GREEN** (R² ≥ 0.98, p90 norm_resid ≤ 0.25 LSB across units):
  implement scale-only storage + in-kernel `α·scale+β`, run the A/B. Recovers
  **~1.30 GB** → brings the ~4.7 GB delta to ~3.4 GB before any other diet step.
- **Symmetric-V GREEN** (inflation ≈ 1.0): the cheaper xmin drop on V alone,
  **~0.65 GB**. Useful if predicted-xmin is GREEN on K but not V.
- **RED on a model**: skip that idea on that model; the xmin really does carry
  independent information there. Fall back to the *shrink* diet (fp8 scale,
  6G option C/F) or accept the density framing.

Stacking (with the 6G shrink options, accounting for overlap — B drops xmin so
C only fp8s the remaining scale tensors):

| stack | recovers | int4 vs bf16 after |
|---|---|---|
| light: **B** (pred-xmin) + fp8-scale + n_protect 5→3 | ~2.3 GB | ~2.4 GB over |
| aggressive: + **D** (inline k_protect, deep kernel) | ~3.1 GB | **~1.5 GB over** |

A **~1 GB floor** (CUDA-graph private pools ~0.62 + misc buffers ~0.4) is **not
diet-addressable** — exact bf16 parity needs graph-capture memory work too, so
the realistic target is "close the gap to ~1.5–2.5 GB," not parity. If the
goal is purely VC-optics, the **density framing** (~1.8× seq/GB at the block
limit) is the cheaper answer and doesn't require any of this.

## Files

- `CTM_plus/Bench/scripts/phase6g2_sidecar_diet_derisk.py` — analyzer:
  `--selftest` (CPU), `--capture` (GPU hook+accumulate), `--analyze` (CPU verdict).
- `CTM_plus/Bench/tests/test_phase6g2_diet_derisk.py` — torch-free CPU regression.
- Inputs reused: `calibrate_phase5b_protect_mask.py` (corpus + hook helpers).
- Upstream context: `PHASE_6G_SIDECAR_DIET_FINDINGS.md` (the audit + the ~2.5 GB
  shrink ceiling), `MEMORY_STORY.md` (the +4.7 GB delta + density story).
