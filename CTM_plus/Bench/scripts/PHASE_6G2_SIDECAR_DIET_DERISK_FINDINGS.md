# Phase 6G.2 — sidecar-diet DE-RISK analyzer (measure before you cut)

> **Status:** code + CPU regression green; **Qwen-7B GPU capture done →
> RED on all three options** (see the verdict section below). This is a
> **screen**, not the final quality verdict: it tells us, per model, whether
> three sidecar-*elimination* ideas are even plausible before we spend
> kernel-engineering or GPU-A/B time on them. On Qwen-7B, none are.

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

## The three ideas this screens

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

### (C) n_protect 5→3 — shrink `k_protect_ext` (~0.33 GB)

**Hypothesis:** the 4th and 5th highest-max-abs channels per (layer, head) carry
negligible overflow risk versus the top-3. If so, reduce `n_protect` from 5 to 3,
saving 2/5 of `k_protect_ext` (~0.82 GB × 40% ≈ **0.33 GB**).

**Decision metric (closed form, exact):** `top3_mass_frac = Σ top-3 max-abs / Σ top-5
max-abs` per head, where max-abs is the running max over the calibration corpus. If
the 4th/5th channels carry near-zero mass their activation range is small → int4 can
absorb it without a bf16 escape lane.

| `top3_mass_frac` (median / p10 worst) | verdict |
|---|---|
| median ≥ 0.90, p10 ≥ 0.85 | **GREEN** (4th/5th are dead weight) |
| median ≥ 0.80, p10 ≥ 0.75 | **YELLOW** |
| else | **RED** (4th/5th cover real overflow risk) |

**(C) is independent of (B)/(A)** — it addresses a different tensor (`k_protect_ext`)
so savings stack. If both (B) and (C) are GREEN, the combined recovery is
**~1.30 + 0.33 = ~1.63 GB**.

The capture uses the same prefill hook: per (layer, head, channel), the running
max-abs over the calibration corpus is already computed for the K quant pass; the
top-5 per head are serialized into `k_protect` in the stats JSON (< 1 KB/layer extra).

All metrics are **closed form** — accumulable online in the capture hook, no
raw-activation dump needed:
- (B)/(A): per-group `(min, max, absmax)` + regression sufficient statistics
- (C): per-channel running max-abs → top-5 per head at serialization

## What's validated (CPU, this container)

No GPU/torch/numpy here, so only the pure-Python decision core — but that's the
load-bearing logic.

- `test_phase6g2_diet_derisk.py` (torch-free, 14/14 PASS): linear regression
  from sufficient statistics vs hand-computed α/β/R²; the closed-form inflation
  identity; per-unit GREEN/YELLOW/RED thresholds; the dead-channel guard; the
  model rollup (one RED unit downgrades GREEN→YELLOW; 10% RED→RED); percentile
  interpolation; n_protect_unit (concentrated/uniform/yellow/dead); the
  recovered-GB constants tied to the 6G inventory (including n_protect_3=0.33).
- `phase6g2_sidecar_diet_derisk.py --selftest` (PASS): regression core
  (exact-fit, const-x, const-y degenerate cases), unit verdicts on tight/noisy/
  dead synthetic data, n_protect unit verdicts, and a full `analyze_model` on a
  2-layer synthetic model with all three options (B, A, C).

## Qwen-7B verdict (GPU capture, 2026-05-29 — RED on all three)

Captured on an A100-80GB: `Qwen/Qwen2.5-7B-Instruct`, 28 attention layers,
55 calibration prompts, block_size=32, v_group_size=32. The capture path ran
clean (no errors), which also validates the GPU hook + accumulator end-to-end.

| option | recovers | verdict | the number that killed it |
|---|---|---|---|
| **(B) predicted-xmin** | 1.30 GB | **RED** | median R²=**0.417** (need 0.98); median residual=**1.83 LSB** (need ≤0.25). 14779/14784 units RED. |
| **(A) symmetric-V** | 0.65 GB | **RED** | median inflation=**1.16**, p90=1.22 (GREEN ≤1.05). 363/448 units RED, 0 GREEN. |
| **(C) n_protect 5→3** | 0.33 GB | **RED** | median top-3/top-5 mass=**0.668** (need ≥0.90); p10=0.632. 111/112 heads RED. |

**Screen result: ~0.00 GB of the +4.7 GB delta is recoverable by elimination
on Qwen-7B.** The weakest layers were the early ones (layers 1–3, green_frac 0.0).

### Why each is RED (the physical reading)

- **(B) xmin is not a function of scale.** The hypothesis was `min ≈ α·range + β`
  (self-similar block shape). R²=0.42 says range explains <half of min's variance:
  the per-channel **mean drifts independently of the spread** across 32-token
  blocks. min and range are two genuine degrees of freedom, so the xmin tensor
  carries real information — reconstructing it would inject ~1.8 LSB of bias into
  *every* dequantized value, ~3.6× the existing ~0.5-LSB quant floor.
- **(A) V groups are offset, not centered.** A 16% median quant-step inflation
  means symmetric V would coarsen every V value by ~16% (worse on the tail) — and
  V is the *un*-protected path, so it would erode the +20.4 pt quality margin for
  only 0.65 GB. Even the "least RED" option isn't near-GREEN.
- **(C) the protected channels are a plateau, not a spike.** top-3/top-5 ≈ 0.67 is
  barely above the 0.60 you'd get from five *equal* channels: the 4th/5th heavy
  hitters are nearly as large as the top-3, so dropping them removes real overflow
  protection. This is consistent with why the protect mask exists at all.

**Conclusion: the sidecar metadata is information-dense, not redundant.** The
+4.7 GB is not recoverable by elimination on this model. Per the run-order
discipline ("if Qwen-7B is GREEN or near-GREEN … then write the spec"), **no
implementation spec is written and no A/B is earned** — RED means stop.

## Still pending (deferred — gated off by the RED verdict)

- **Mistral-7B / Llama-3.1-8B / Qwen-14B captures** — the run-order only repeats
  "if promising." Qwen-7B is decisively not, and these are architectural
  properties of asymmetric per-block quant, so corroboration is **optional**, not
  required. (One confirmation run is cheap if you want to prove it's not
  Qwen-specific — same command, swap `--model`.)
- **The downstream A/B (the real gate)** — moot for elimination on Qwen-7B, since
  nothing passed the screen. Recorded for completeness: even a GREEN screen only
  earns a token-agreement + hard-needle A/B vs the current asymmetric sidecars;
  the screen bounds *quant* error, not *model output*.

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

## How to read the result (reference — what GREEN would have meant)

Qwen-7B came back RED on all three (above); this is the decision table the screen
applies, kept for the remaining models and as the threshold rationale:

- **Predicted-xmin GREEN** (R² ≥ 0.98, p90 norm_resid ≤ 0.25 LSB across units):
  implement scale-only storage + in-kernel `α·scale+β`, run the A/B. Recovers
  **~1.30 GB** → brings the ~4.7 GB delta to ~3.4 GB before any other diet step.
- **Symmetric-V GREEN** (inflation ≈ 1.0): the cheaper xmin drop on V alone,
  **~0.65 GB**. Useful if predicted-xmin is GREEN on K but not V.
- **n_protect 5→3 GREEN** (median top3_mass_frac ≥ 0.90): reduce protected
  channels from 5 to 3, shrinking `k_protect_ext` by 40%. Recovers **~0.33 GB**,
  independent of (B)/(A). Stack with predicted-xmin for **~1.63 GB** combined.
- **RED on a model for any option** (← Qwen-7B, all three): skip that idea on that
  model; fall back to the *shrink* diet (fp8 scale, 6G option C/F) or accept the
  density framing. **For Qwen-7B the disposition is the density framing** — the
  shrink diet is capacity-negative per 6G, and elimination is off the table.

Stacking (with the 6G shrink options, accounting for overlap — B drops xmin so
C only fp8s the remaining scale tensors):

| stack | recovers | int4 vs bf16 after |
|---|---|---|
| **B** (pred-xmin) + **n_protect 5→3 (C)** | ~1.63 GB | ~3.1 GB over |
| light: **B** + **C** + fp8-scale | ~2.3 GB | ~2.4 GB over |
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
